# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Tests for the host-supplied module availability gate.

The gate is authoritative host state, not model input: it never consults
Flyto2 Core and it must not change behavior when the host supplies nothing.
"""
import pytest

from conftest import make_workflow
from flyto_blueprint.availability import (
    MODULE_UNAVAILABLE_CODE,
    is_blueprint_available,
    missing_module_ids,
    normalize_available_module_ids,
)

BROWSER_SCRAPE_MODULES = [
    "browser.launch",
    "browser.goto",
    "browser.wait",
    "browser.extract",
]
LEARNED_MODULES = ["math.add", "string.reverse", "array.sort"]


def _ids(summaries):
    return [summary["id"] for summary in summaries]


class TestBackwardCompatibility:
    """``None`` means the host made no claim; nothing may change."""

    def test_list_default_matches_explicit_none(self, engine):
        assert _ids(engine.list_blueprints()) == _ids(engine.list_blueprints(None))

    def test_search_default_matches_explicit_none(self, engine):
        assert _ids(engine.search("browser scrape")) == _ids(
            engine.search("browser scrape", None),
        )

    def test_list_none_keeps_full_catalog(self, engine):
        assert len(engine.list_blueprints(None)) == len(engine.list_blueprints())
        assert "browser_scrape" in _ids(engine.list_blueprints(None))

    def test_expand_default_matches_explicit_none(self, engine):
        args = {"url": "https://example.com", "extract_selector": "#data"}
        assert engine.expand("browser_scrape", args)["data"]["steps"] == (
            engine.expand("browser_scrape", args, None)["data"]["steps"]
        )

    def test_abstract_modules_still_expand_without_host_input(self, engine):
        """Unknown/abstract module names stay allowed with no authoritative set."""
        workflow = make_workflow(tag="abstract_ok")
        workflow["steps"][0]["module"] = "totally.unknown.module"
        learned = engine.learn_from_workflow(workflow, name="abstract_ok")
        blueprint_id = learned["data"]["id"]

        result = engine.expand(blueprint_id, {
            "a": 1, "b": 2, "text": "x", "array": [], "tag": "abstract_ok",
        })

        assert result["ok"] is True
        assert blueprint_id in _ids(engine.list_blueprints())

    def test_not_found_is_unchanged_under_gate(self, engine):
        result = engine.expand("nonexistent_xyz", {}, [])
        assert result["ok"] is False
        assert "code" not in result

    def test_missing_args_still_checked_when_modules_available(self, engine):
        result = engine.expand("browser_scrape", {}, BROWSER_SCRAPE_MODULES)
        assert result["ok"] is False
        assert "missing" in result["error"].lower()
        assert "code" not in result


class TestFiltering:
    """A supplied set filters list/search to what the host can run."""

    def test_list_keeps_only_supported_blueprints(self, engine):
        listed = _ids(engine.list_blueprints(BROWSER_SCRAPE_MODULES))
        assert "browser_scrape" in listed
        assert "api_get" not in listed
        assert listed != _ids(engine.list_blueprints())

    def test_search_keeps_only_supported_blueprints(self, engine):
        results = _ids(engine.search("scrape", BROWSER_SCRAPE_MODULES))
        assert "browser_scrape" in results
        assert all(bp_id != "scrape_and_save" for bp_id in results)

    def test_search_is_a_subset_of_unfiltered_search(self, engine):
        filtered = _ids(engine.search("scrape", BROWSER_SCRAPE_MODULES))
        assert set(filtered) <= set(_ids(engine.search("scrape")))

    def test_composition_block_modules_are_required(self, engine):
        """browser_scrape composes browser_init, so its modules count too."""
        without_block = ["browser.wait", "browser.extract"]
        assert "browser_scrape" not in _ids(engine.list_blueprints(without_block))

        result = engine.expand(
            "browser_scrape",
            {"url": "https://example.com", "extract_selector": "#data"},
            without_block,
        )
        assert result["ok"] is False
        assert result["code"] == MODULE_UNAVAILABLE_CODE
        assert result["missing_module_ids"] == ["browser.goto", "browser.launch"]

    def test_learned_blueprint_is_filtered_by_its_modules(self, engine):
        engine.learn_from_workflow(make_workflow(tag="gate_f"), name="gate_filtered")
        assert "gate_filtered" in _ids(engine.list_blueprints(LEARNED_MODULES))
        assert "gate_filtered" not in _ids(
            engine.list_blueprints(["math.add", "string.reverse"]),
        )

    def test_listed_blueprints_always_expand_past_the_gate(self, engine):
        """List and expand agree: nothing listed can fail the gate."""
        for summary in engine.list_blueprints(BROWSER_SCRAPE_MODULES):
            result = engine.expand(summary["id"], {}, BROWSER_SCRAPE_MODULES)
            assert result.get("code") != MODULE_UNAVAILABLE_CODE

    def test_rejects_bare_string_instead_of_splitting_characters(self, engine):
        with pytest.raises(TypeError):
            engine.list_blueprints("browser.goto")


class TestStrictHostInput:
    """Malformed host input is rejected, never silently repaired.

    Dropping a bad entry would narrow the set below what the host claimed, so a
    blueprint would be hidden or refused for a reason no error names. Every
    entry point raises instead of gating on a set the host never meant.
    """

    # A str/bytes-like object is iterable, so an unguarded gate would filter
    # on single characters or integers.
    STRINGY = [
        "browser.goto",
        b"browser.goto",
        bytearray(b"browser.goto"),
        memoryview(b"browser.goto"),
    ]
    # Not iterable at all, or iterating raises: never a module ID collection.
    MALFORMED = [7, 4.2, True, object(), min]
    # Iterable, but an entry is not a module ID string.
    BAD_ENTRIES = [
        ["browser.goto", None],
        ["browser.goto", 7],
        ["browser.goto", ["browser.wait"]],
        ["browser.goto", b"browser.wait"],
        [{"module": "browser.goto"}],
    ]
    # Iterable of strings, but an entry cannot name a real module.
    BLANK_ENTRIES = ["", " ", "\t", "\n", "   \t  "]
    PADDED_ENTRIES = [" browser.goto", "browser.goto ", "\tbrowser.goto\n"]

    @pytest.mark.parametrize("value", STRINGY)
    def test_string_like_is_rejected(self, value):
        with pytest.raises(TypeError):
            normalize_available_module_ids(value)

    @pytest.mark.parametrize("value", MALFORMED)
    def test_malformed_iterable_is_rejected(self, value):
        with pytest.raises(TypeError):
            normalize_available_module_ids(value)

    def test_iterable_raising_type_error_is_rejected(self):
        class Hostile:
            def __iter__(self):
                raise TypeError("not really iterable")

        with pytest.raises(TypeError):
            normalize_available_module_ids(Hostile())

    @pytest.mark.parametrize("value", BAD_ENTRIES)
    def test_non_string_entry_is_rejected(self, value):
        with pytest.raises(TypeError):
            normalize_available_module_ids(value)

    @pytest.mark.parametrize("entry", BLANK_ENTRIES)
    def test_blank_entry_is_rejected(self, entry):
        with pytest.raises(ValueError):
            normalize_available_module_ids(["browser.goto", entry])

    @pytest.mark.parametrize("entry", PADDED_ENTRIES)
    def test_padded_entry_is_rejected_not_stripped(self, entry):
        with pytest.raises(ValueError):
            normalize_available_module_ids([entry])

    def test_blank_entry_is_value_error_not_type_error(self):
        """The two failure modes stay distinguishable for the host."""
        with pytest.raises(ValueError):
            normalize_available_module_ids([""])
        with pytest.raises(TypeError):
            normalize_available_module_ids([None])

    def test_valid_input_normalizes_to_one_frozen_set(self):
        result = normalize_available_module_ids(["b.a", "b.b", "b.a"])
        assert result == frozenset({"b.a", "b.b"})
        assert isinstance(result, frozenset)

    def test_none_stays_none_and_empty_stays_empty(self):
        assert normalize_available_module_ids(None) is None
        assert normalize_available_module_ids([]) == frozenset()

    def test_generator_is_accepted_and_consumed_once(self):
        calls = []

        def source():
            for module_id in BROWSER_SCRAPE_MODULES:
                calls.append(module_id)
                yield module_id

        assert normalize_available_module_ids(source()) == frozenset(
            BROWSER_SCRAPE_MODULES,
        )
        assert calls == BROWSER_SCRAPE_MODULES

    def test_dict_keys_and_sets_are_accepted(self):
        expected = frozenset(BROWSER_SCRAPE_MODULES)
        assert normalize_available_module_ids(
            dict.fromkeys(BROWSER_SCRAPE_MODULES),
        ) == expected
        assert normalize_available_module_ids(set(BROWSER_SCRAPE_MODULES)) == expected
        assert normalize_available_module_ids(
            tuple(BROWSER_SCRAPE_MODULES),
        ) == expected

    @pytest.mark.parametrize("bad", [["browser.goto", ""], ["browser.goto", 7]])
    def test_every_entry_point_rejects_the_same_input(self, engine, bad):
        """list, search, and expand share one normalization, so all three raise."""
        with pytest.raises((TypeError, ValueError)):
            engine.list_blueprints(bad)
        with pytest.raises((TypeError, ValueError)):
            engine.search("scrape", bad)
        with pytest.raises((TypeError, ValueError)):
            engine.expand("browser_scrape", {}, bad)

    def test_rejection_precedes_blueprint_lookup(self, engine):
        """Malformed input raises rather than returning a not-found result."""
        with pytest.raises(ValueError):
            engine.expand("nonexistent_xyz", {}, [""])

    def test_rejection_leaves_stored_blueprint_untouched(
        self, engine, memory_backend,
    ):
        learned = engine.learn_from_workflow(
            make_workflow(tag="strict_no_mutate"), name="strict_no_mutate_bp",
        )
        blueprint_id = learned["data"]["id"]
        before = memory_backend.load_one(blueprint_id)

        with pytest.raises(TypeError):
            engine.expand(blueprint_id, {}, ["math.add", None])

        assert memory_backend.load_one(blueprint_id) == before


class TestDynamicModules:
    """A ``{{arg}}`` module name is never assumed available."""

    FILE_HOST = ["file.read", "file.write"]
    FILE_ARGS = {"input_path": "in.txt", "output_path": "out.txt"}

    def test_dynamic_blueprint_is_hidden_from_list_and_search(self, engine):
        """file_transform runs ``{{operation}}``, so it cannot be proven runnable."""
        host = self.FILE_HOST + ["string.uppercase"]
        assert "file_transform" in _ids(engine.list_blueprints())
        assert "file_transform" not in _ids(engine.list_blueprints(host))
        assert "file_transform" not in _ids(engine.search("transform file", host))

    def test_expand_gates_the_resolved_module(self, engine):
        result = engine.expand(
            "file_transform",
            {**self.FILE_ARGS, "operation": "shell.execute"},
            self.FILE_HOST,
        )
        assert result["ok"] is False
        assert result["code"] == MODULE_UNAVAILABLE_CODE
        assert result["missing_module_ids"] == ["shell.execute"]

    def test_expand_allows_a_resolved_available_module(self, engine):
        result = engine.expand(
            "file_transform",
            {**self.FILE_ARGS, "operation": "string.uppercase"},
            self.FILE_HOST + ["string.uppercase"],
        )
        assert result["ok"] is True

    def test_unresolved_module_fails_closed_in_expand(self, engine):
        result = engine.expand("file_transform", self.FILE_ARGS, self.FILE_HOST)
        assert result["code"] == MODULE_UNAVAILABLE_CODE
        assert result["missing_module_ids"] == ["{{operation}}"]

    def test_dynamic_module_still_expands_without_host_input(self, engine):
        result = engine.expand(
            "file_transform",
            {**self.FILE_ARGS, "operation": "string.uppercase"},
        )
        assert result["ok"] is True

    def test_skipped_optional_step_module_is_not_required(self, engine):
        host = ["browser.launch", "browser.goto", "browser.extract"]
        args = {"url": "https://x.com", "extract_selector": "#d"}

        assert engine.expand("browser_scrape", args, host)["ok"] is True

        gated = engine.expand(
            "browser_scrape", {**args, "wait_selector": ".loaded"}, host,
        )
        assert gated["code"] == MODULE_UNAVAILABLE_CODE
        assert gated["missing_module_ids"] == ["browser.wait"]


class TestUnresolvedTemplateBeatsHostSetMembership:
    """A literal ``{{arg}}`` entry in the host set never proves availability.

    ``{{operation}}`` in ``available_module_ids`` is a token that collides with
    an unsubstituted placeholder, not a module the host can execute. If exact
    membership were checked first, that collision would clear the gate for every
    blueprint whose module name never resolved, and list, search, and expand
    would each publish a blueprint the host cannot run. The template check
    therefore runs independently of membership; resolved IDs still have to match
    the host set exactly.
    """

    FILE_HOST = ["file.read", "file.write"]
    FILE_ARGS = {"input_path": "in.txt", "output_path": "out.txt"}
    # The host set literally contains the unresolved token.
    SPOOFED_HOST = FILE_HOST + ["{{operation}}"]

    def test_search_finds_the_blueprint_without_a_host_claim(self, engine):
        """Guards the two hiding assertions below from passing vacuously."""
        assert "file_transform" in _ids(engine.search("transform file"))
        assert "file_transform" in _ids(engine.list_blueprints())

    def test_list_hides_it_despite_the_token_being_in_the_host_set(self, engine):
        assert "file_transform" not in _ids(
            engine.list_blueprints(self.SPOOFED_HOST),
        )

    def test_search_hides_it_despite_the_token_being_in_the_host_set(self, engine):
        assert "file_transform" not in _ids(
            engine.search("transform file", self.SPOOFED_HOST),
        )

    def test_expand_reports_the_token_as_missing(self, engine):
        result = engine.expand("file_transform", self.FILE_ARGS, self.SPOOFED_HOST)

        assert result["ok"] is False
        assert result["code"] == MODULE_UNAVAILABLE_CODE
        assert result["missing_module_ids"] == ["{{operation}}"]
        assert "{{operation}}" in result["error"]
        assert "data" not in result

    def test_expand_is_identical_with_and_without_the_token_in_the_host_set(
        self, engine,
    ):
        """Adding the token to the host set changes nothing at all."""
        assert engine.expand(
            "file_transform", self.FILE_ARGS, self.SPOOFED_HOST,
        ) == engine.expand("file_transform", self.FILE_ARGS, self.FILE_HOST)

    def test_args_path_that_leaves_the_module_unresolved_fails_closed(self, engine):
        """Other args substitute; ``operation`` is absent, so the gate holds."""
        result = engine.expand(
            "file_transform",
            {**self.FILE_ARGS, "operation_params": {"suffix": "!"}},
            self.SPOOFED_HOST,
        )

        assert result["code"] == MODULE_UNAVAILABLE_CODE
        assert result["missing_module_ids"] == ["{{operation}}"]

    def test_resolved_module_still_matches_the_host_set_exactly(self, engine):
        """The token in the set does not widen the gate for resolved IDs."""
        args = {**self.FILE_ARGS, "operation": "string.uppercase"}

        blocked = engine.expand("file_transform", args, self.SPOOFED_HOST)
        assert blocked["code"] == MODULE_UNAVAILABLE_CODE
        assert blocked["missing_module_ids"] == ["string.uppercase"]

        allowed = engine.expand(
            "file_transform", args, self.SPOOFED_HOST + ["string.uppercase"],
        )
        assert allowed["ok"] is True

    def test_none_stays_permissive_for_an_unresolved_module(self, engine):
        """No host claim means no gate, even for a template module name."""
        result = engine.expand("file_transform", self.FILE_ARGS)

        assert result.get("code") != MODULE_UNAVAILABLE_CODE
        assert "file_transform" in _ids(engine.list_blueprints(None))

    def test_partially_substituted_module_name_is_unavailable(self):
        """Unresolved means any leftover placeholder, not just a whole token."""
        bp = {"steps": [{"id": "s1", "module": "{{namespace}}.{{operation}}"}]}
        host = normalize_available_module_ids([
            "string.uppercase", "string.{{operation}}",
        ])

        assert missing_module_ids(
            bp, host, None, {"namespace": "string"},
        ) == ["string.{{operation}}"]
        assert is_blueprint_available(bp, host) is False

    def test_token_missing_ids_are_sorted_and_deduplicated(self):
        """Determinism holds for token entries exactly as for resolved IDs."""
        bp = {"steps": [
            {"id": "s1", "module": "{{op_b}}"},
            {"id": "s2", "module": "{{op_a}}"},
            {"id": "s3", "module": "{{op_b}}"},
            {"id": "s4", "module": "file.read"},
        ]}
        entries = ["{{op_a}}", "{{op_b}}", "file.read"]

        expected = ["{{op_a}}", "{{op_b}}"]
        assert missing_module_ids(
            bp, normalize_available_module_ids(entries),
        ) == expected
        assert missing_module_ids(
            bp, normalize_available_module_ids(reversed(entries)),
        ) == expected

    def test_none_host_set_reports_nothing_for_token_modules(self):
        bp = {"steps": [{"id": "s1", "module": "{{operation}}"}]}

        assert missing_module_ids(bp, None) == []
        assert is_blueprint_available(bp, None) is True


class TestEmptySet:
    """An empty collection is a real claim: no module is available."""

    def test_empty_list_returns_no_blueprints(self, engine):
        assert engine.list_blueprints([]) == []

    def test_empty_set_returns_no_search_results(self, engine):
        assert engine.search("scrape", set()) == []
        assert engine.search("", set()) == []

    def test_empty_set_blocks_expand(self, engine):
        result = engine.expand(
            "browser_scrape",
            {
                "url": "https://example.com",
                "extract_selector": "#data",
                "wait_selector": ".loaded",
            },
            [],
        )
        assert result["ok"] is False
        assert result["code"] == MODULE_UNAVAILABLE_CODE
        assert result["missing_module_ids"] == sorted(BROWSER_SCRAPE_MODULES)

    def test_empty_set_is_not_none(self, engine):
        assert engine.list_blueprints([]) != engine.list_blueprints(None)


class TestDeterministicError:

    def test_missing_ids_are_sorted_and_unique(self, engine):
        workflow = make_workflow(tag="dup_mod")
        workflow["steps"][2]["module"] = "math.add"
        learned = engine.learn_from_workflow(workflow, name="dup_mod_bp")
        blueprint_id = learned["data"]["id"]

        result = engine.expand(blueprint_id, {}, ["string.reverse"])

        assert result["missing_module_ids"] == ["math.add"]

    def test_error_is_stable_across_input_order(self, engine):
        args = {
            "url": "https://example.com",
            "extract_selector": "#data",
            "wait_selector": ".loaded",
        }
        first = engine.expand("browser_scrape", args, ["browser.goto"])
        second = engine.expand("browser_scrape", args, {"browser.goto"})
        assert first == second
        assert first["missing_module_ids"] == [
            "browser.extract", "browser.launch", "browser.wait",
        ]

    def test_error_shape(self, engine):
        result = engine.expand("browser_scrape", {}, [])
        assert result["ok"] is False
        assert result["code"] == MODULE_UNAVAILABLE_CODE
        assert isinstance(result["missing_module_ids"], list)
        assert "browser.launch" in result["error"]
        assert "data" not in result


class TestNoScoreOrUseMutation:
    """The gate runs before scoring, use recording, and expansion."""

    def test_use_count_and_score_are_untouched(self, engine, memory_backend):
        learned = engine.learn_from_workflow(
            make_workflow(tag="no_mutate"), name="no_mutate_bp",
        )
        blueprint_id = learned["data"]["id"]
        before = memory_backend.load_one(blueprint_id)

        for _ in range(3):
            result = engine.expand(blueprint_id, {}, ["math.add"])
            assert result["code"] == MODULE_UNAVAILABLE_CODE

        after = memory_backend.load_one(blueprint_id)
        assert after.get("use_count", 0) == before.get("use_count", 0)
        assert after.get("score") == before.get("score")
        assert after == before

    def test_use_count_still_increments_when_gate_passes(self, engine, memory_backend):
        learned = engine.learn_from_workflow(
            make_workflow(tag="gate_pass"), name="gate_pass_bp",
        )
        blueprint_id = learned["data"]["id"]

        result = engine.expand(blueprint_id, {
            "a": 1, "b": 2, "text": "x", "array": [], "tag": "gate_pass",
        }, LEARNED_MODULES)

        assert result["ok"] is True
        assert memory_backend.load_one(blueprint_id).get("use_count", 0) == 1


class TestNotModelFacing:
    """The host passes availability internally; no tool schema exposes it."""

    def test_tool_schemas_have_no_availability_input(self):
        from flyto_blueprint.tools import get_blueprint_tools

        for tool in get_blueprint_tools():
            properties = tool["inputSchema"].get("properties", {})
            assert "available_module_ids" not in properties

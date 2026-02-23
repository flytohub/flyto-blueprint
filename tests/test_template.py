# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for {{arg}} substitution and type preservation."""
from flyto_blueprint.template import abstract_params, substitute, substitute_deep


class TestSubstitute:

    def test_simple_replacement(self):
        assert substitute("{{url}}", {"url": "https://example.com"}) == "https://example.com"

    def test_missing_arg_kept(self):
        assert substitute("{{missing}}", {}) == "{{missing}}"

    def test_multiple_placeholders(self):
        result = substitute("Go to {{url}} and click {{selector}}", {
            "url": "https://x.com", "selector": "#btn",
        })
        assert result == "Go to https://x.com and click #btn"

    def test_non_string_passthrough(self):
        assert substitute(42, {"x": "y"}) == 42


class TestSubstituteDeep:

    def test_string_substitution(self):
        assert substitute_deep("{{x}}", {"x": "hello"}) == "hello"

    def test_type_preservation_int(self):
        result = substitute_deep("{{count}}", {"count": 42})
        assert result == 42
        assert isinstance(result, int)

    def test_type_preservation_bool(self):
        result = substitute_deep("{{flag}}", {"flag": True})
        assert result is True

    def test_type_preservation_dict(self):
        result = substitute_deep("{{data}}", {"data": {"k": "v"}})
        assert result == {"k": "v"}

    def test_type_preservation_list(self):
        result = substitute_deep("{{items}}", {"items": [1, 2, 3]})
        assert result == [1, 2, 3]

    def test_dict_recursion(self):
        obj = {"url": "{{url}}", "count": "{{n}}"}
        result = substitute_deep(obj, {"url": "https://x.com", "n": 5})
        assert result == {"url": "https://x.com", "count": 5}

    def test_list_recursion(self):
        obj = ["{{a}}", "{{b}}"]
        result = substitute_deep(obj, {"a": 1, "b": 2})
        assert result == [1, 2]

    def test_nested_dict_in_list(self):
        obj = [{"key": "{{v}}"}]
        result = substitute_deep(obj, {"v": "val"})
        assert result == [{"key": "val"}]

    def test_partial_template_stays_string(self):
        result = substitute_deep("prefix_{{x}}_suffix", {"x": "mid"})
        assert result == "prefix_mid_suffix"
        assert isinstance(result, str)


class TestAbstractParams:

    def test_constants_kept(self):
        args_def = {}
        result = abstract_params({"headless": True, "url": "https://x.com"}, args_def)
        assert result["headless"] is True
        assert result["url"] == "{{url}}"
        assert "url" in args_def

    def test_step_ref_kept(self):
        args_def = {}
        result = abstract_params({"text": "${steps.s1.result}"}, args_def)
        assert result["text"] == "${steps.s1.result}"
        assert "text" not in args_def

    def test_existing_template_kept(self):
        args_def = {}
        result = abstract_params({"url": "{{url}}"}, args_def)
        assert result["url"] == "{{url}}"

    def test_type_detection_bool(self):
        args_def = {}
        abstract_params({"flag": True}, args_def)
        assert args_def["flag"]["type"] == "boolean"

    def test_type_detection_number(self):
        args_def = {}
        abstract_params({"count": 42}, args_def)
        assert args_def["count"]["type"] == "number"

    def test_type_detection_dict(self):
        args_def = {}
        abstract_params({"data": {"k": "v"}}, args_def)
        assert args_def["data"]["type"] == "object"

    def test_type_detection_list(self):
        args_def = {}
        abstract_params({"items": [1, 2]}, args_def)
        assert args_def["items"]["type"] == "array"

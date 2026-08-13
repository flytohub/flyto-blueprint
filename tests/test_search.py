# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Tests for listing, ranking, relevance, and retired-hidden behavior."""
import copy
import hashlib
import json

import pytest

from conftest import make_workflow, make_workflow_alt
from flyto_blueprint.intent import (
    CapabilitySearchBoundaryError,
    build_capability_search_document,
    build_capability_search_request,
    build_capability_search_tombstone,
    capability_projection_is_indexable,
    decode_capability_search_cursor,
    encode_capability_search_cursor,
    validate_capability_search_document,
    validate_capability_search_mutation,
    validate_capability_search_page,
    validate_capability_search_projection,
    validate_capability_search_request,
    validate_capability_search_tombstone,
)


def _projection():
    return {
        "search_version": "flyto.capability-search.v1", "card_version": "flyto.capability-card.v1",
        "tenant_id": "tenant-1", "space_id": "space-1", "capability_id": "capability-1",
        "content_digest": "sha256:" + "a" * 64, "semantic_origin": "declared", "source_kind": "software.package",
        "title": "Bounded document extraction", "summary": "Extract text from a supplied document.",
        "semantic_ids": {"intents": ["document.extract"], "affordances": ["text.read"], "effects": ["text.available"], "events": ["document.supplied"]},
        "approved": True, "host_verified": True, "verified": True, "active": True,
        "retired": False, "complete": True, "trust_state": "approved_verified",
        "autonomous_routable": True, "audit_visible": True,
    }


def _model():
    return {"model_id": "neutral.model", "model_version": "v1", "dimensions": 384, "model_digest": "sha256:" + "b" * 64}


def _filters():
    return {"tenant_id": "tenant-1", "space_id": "space-1", "status": "active", "acl_principals": ["principal-1"], "acl_scopes": ["scope.read"], "risk_classification": "medium", "resource_ids": ["resource-1"], "capability_ids": ["capability-1"]}


def _projection_for_state(state):
    projection = _projection()
    if state == "retired":
        projection.update(retired=True, autonomous_routable=False)
    elif state == "inactive":
        projection.update(active=False, autonomous_routable=False)
    elif state == "incomplete":
        projection.update(complete=False, autonomous_routable=False)
    elif state == "draft_unapproved":
        projection.update(approved=False, autonomous_routable=False)
    elif state == "draft_unverified":
        projection.update(verified=False, autonomous_routable=False)
    projection["trust_state"] = state
    return projection


class HostileMapping(dict):
    def keys(self):
        raise RuntimeError("secret-runtime")


class HostileList(list):
    def __iter__(self):
        raise RuntimeError("secret-runtime")


def _assert_redacted(call, *args):
    with pytest.raises(CapabilitySearchBoundaryError) as caught:
        call(*args)
    assert str(caught.value) in {
        "CAPABILITY_SEARCH_INVALID", "CAPABILITY_SEARCH_TAMPERED",
        "CAPABILITY_SEARCH_CURSOR_INVALID", "CAPABILITY_SEARCH_NOT_INDEXABLE",
        "CAPABILITY_SEARCH_STILL_INDEXABLE",
    }
    assert "secret" not in str(caught.value)


def _bind_candidate(candidate):
    candidate["candidate_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()
    return candidate


def _candidate(request, capability_id="capability-1", score=900):
    return _bind_candidate({
        "tenant_id": "tenant-1", "space_id": "space-1", "capability_id": capability_id,
        "status": "active", "acl_principals": ["principal-1"], "acl_scopes": ["scope.read"],
        "risk_classification": "low", "resource_ids": ["resource-1"], "score": score,
        "source_projection_digest": "sha256:" + "e" * 64,
        "upstream_content_digest": "sha256:" + "a" * 64,
        "document_digest": "sha256:" + "f" * 64,
        "model_digest": _model()["model_digest"], "index_digest": request["index_digest"],
        "snapshot_digest": request["snapshot_digest"], "candidate_only": True,
        "execution_authority": False,
    })


class TestCapabilitySearchContract:

    @pytest.mark.parametrize("origin", ["declared", "static_derived"])
    @pytest.mark.parametrize("source_kind", ["hardware.sensor", "software.package", "workflow.http", "mcp.tool@v1"])
    def test_exact_upstream_projection_dialect(self, origin, source_kind):
        projection = _projection()
        projection.update(semantic_origin=origin, source_kind=source_kind, capability_id="capability@v1")
        assert validate_capability_search_projection(projection) == projection

    @pytest.mark.parametrize("state", ["approved_verified", "retired", "inactive", "incomplete", "draft_unapproved", "draft_unverified"])
    def test_every_upstream_trust_state_is_valid_audit_data(self, state):
        projection = _projection_for_state(state)
        assert validate_capability_search_projection(projection)["trust_state"] == state
        assert capability_projection_is_indexable(projection) is (state == "approved_verified")

    def test_empty_incomplete_projection_is_valid_but_never_synthesized(self):
        projection = _projection()
        projection.update(title="", summary="", source_kind=None, complete=False, trust_state="incomplete", autonomous_routable=False)
        projection["semantic_ids"] = {name: [] for name in ("intents", "affordances", "effects", "events")}
        assert validate_capability_search_projection(projection) == projection
        assert capability_projection_is_indexable(projection) is False
        with pytest.raises(CapabilitySearchBoundaryError):
            build_capability_search_document(projection, _model(), _filters())

    def test_null_source_projection_is_valid_audit_data_but_not_indexable(self):
        projection = _projection_for_state("incomplete")
        projection["source_kind"] = None
        assert validate_capability_search_projection(projection)["source_kind"] is None
        assert capability_projection_is_indexable(projection) is False

    @pytest.mark.parametrize("field", ["tenant_id", "space_id", "capability_id", "source_kind"])
    def test_projection_identifier_bounds_match_upstream(self, field):
        projection = _projection()
        projection[field] = "a" * 192
        assert validate_capability_search_projection(projection)[field] == "a" * 192
        projection[field] += "a"
        _assert_redacted(validate_capability_search_projection, projection)

    @pytest.mark.parametrize("semantic_field", ["intents", "affordances", "effects", "events"])
    def test_projection_semantic_identifier_bounds_match_upstream(self, semantic_field):
        projection = _projection()
        projection["semantic_ids"][semantic_field] = ["a" * 192]
        assert validate_capability_search_projection(projection)["semantic_ids"][semantic_field] == ["a" * 192]
        projection["semantic_ids"][semantic_field] = ["a" * 193]
        _assert_redacted(validate_capability_search_projection, projection)

    @pytest.mark.parametrize("field", ["title", "summary"])
    def test_projection_display_text_bounds_match_upstream(self, field):
        projection = _projection()
        projection[field] = "a" * 2000
        assert validate_capability_search_projection(projection)[field] == "a" * 2000
        projection[field] += "a"
        _assert_redacted(validate_capability_search_projection, projection)

    def test_projection_display_dialect_preserves_whitespace_and_private_use(self):
        projection = _projection()
        projection.update(title="  title\ue000  ", summary=" summary ")
        assert validate_capability_search_projection(projection)["title"] == "  title\ue000  "
        whitespace = copy.deepcopy(projection)
        whitespace.update(title=" \ue000 ", summary="   ", complete=False, trust_state="incomplete", autonomous_routable=False)
        assert capability_projection_is_indexable(whitespace) is False
        for unsafe in ("bad\x00text", "bad\u200btext", "bad\ud800text"):
            invalid = _projection()
            invalid["title"] = unsafe
            _assert_redacted(validate_capability_search_projection, invalid)

    def test_semantic_projection_exact_32_item_bound(self):
        projection = _projection()
        projection["semantic_ids"]["intents"] = ["intent-{:02d}".format(index) for index in range(32)]
        assert len(validate_capability_search_projection(projection)["semantic_ids"]["intents"]) == 32
        projection["semantic_ids"]["intents"].append("intent-32")
        _assert_redacted(validate_capability_search_projection, projection)

    def test_maximum_projection_builds_and_validates_derived_document(self):
        projection = _projection()
        projection.update(title="t" * 2000, summary="s" * 2000)
        projection["semantic_ids"] = {
            name: ["{}-{}".format(name[0], str(index).zfill(190)) for index in range(32)]
            for name in ("intents", "affordances", "effects", "events")
        }
        document = build_capability_search_document(projection, _model(), _filters())
        assert validate_capability_search_document(document) == document

    def test_192_character_identity_survives_document_request_cursor_and_page(self):
        long_id = "a" * 192
        projection = _projection()
        projection.update(tenant_id=long_id, space_id=long_id, capability_id=long_id)
        filters = _filters()
        filters.update(tenant_id=long_id, space_id=long_id, capability_ids=[long_id])
        document = build_capability_search_document(projection, _model(), filters)
        assert validate_capability_search_document(document)["filters"]["capability_ids"] == [long_id]
        request = build_capability_search_request("query", 2, filters, _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        candidate = _candidate(request, long_id, 900)
        candidate.update(tenant_id=long_id, space_id=long_id)
        candidate.pop("candidate_digest")
        _bind_candidate(candidate)
        page = {"page_version": "flyto.capability-search-page.v1", "request_digest": request["request_digest"], "candidates": [candidate], "next_cursor": None, "candidate_only": True, "execution_authority": False}
        assert validate_capability_search_page(page, request)["candidates"][0]["capability_id"] == long_id
        cursor = encode_capability_search_cursor(request, 900, long_id, b"bounded-test-integrity-key", emitted_count=1)
        assert decode_capability_search_cursor(cursor, request, b"bounded-test-integrity-key")["last_capability_id"] == long_id
        invalid = copy.deepcopy(filters)
        invalid["capability_ids"] = ["a" * 193]
        _assert_redacted(build_capability_search_request, "query", 2, invalid, _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)

    def test_hostile_and_excessive_json_is_always_redacted(self):
        projection = _projection()
        projection["semantic_ids"]["intents"] = HostileList(["hidden"])
        _assert_redacted(validate_capability_search_projection, projection)
        _assert_redacted(validate_capability_search_projection, HostileMapping())
        deep = _projection()
        nested = []
        for _ in range(12):
            nested = [nested]
        deep["semantic_ids"]["intents"] = nested
        _assert_redacted(validate_capability_search_projection, deep)
        huge = _projection()
        huge["summary"] = "x" * 40000
        _assert_redacted(validate_capability_search_projection, huge)
        nodes = _projection()
        nodes["semantic_ids"]["intents"] = ["n{}".format(index) for index in range(600)]
        _assert_redacted(validate_capability_search_projection, nodes)

    def test_validation_returns_detached_json(self):
        projection = _projection()
        clean = validate_capability_search_projection(projection)
        projection["semantic_ids"]["intents"][0] = "mutated"
        assert clean["semantic_ids"]["intents"] == ["document.extract"]

    def test_all_read_boundaries_redact_hostile_and_malformed_shapes(self):
        request = build_capability_search_request("query", 1, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        key = b"bounded-test-integrity-key"
        cases = (
            (validate_capability_search_document, (HostileMapping(),)),
            (validate_capability_search_document, ({},)),
            (validate_capability_search_mutation, (HostileMapping(),)),
            (validate_capability_search_tombstone, ({"retired": True},)),
            (validate_capability_search_request, (HostileMapping(),)),
            (validate_capability_search_page, ({}, request)),
            (validate_capability_search_page, (HostileMapping(), request)),
            (decode_capability_search_cursor, ("not-a-cursor", request, key)),
            (decode_capability_search_cursor, ("x" * 5000, request, key)),
        )
        for call, args in cases:
            _assert_redacted(call, *args)

    def test_tombstone_rebuilds_from_minimal_prior_identity(self):
        identity = {"tenant_id": "tenant-1", "space_id": "space-1", "capability_id": "capability@v1", "source_projection_digest": "sha256:" + "a" * 64, "upstream_content_digest": "sha256:" + "b" * 64, "document_digest": "sha256:" + "c" * 64}
        first = build_capability_search_tombstone(identity, "source.deleted", operation="delete")
        second = build_capability_search_tombstone(json.loads(json.dumps(identity)), "source.deleted", operation="delete")
        assert first == second == validate_capability_search_tombstone(first)
        assert not any(field in first for field in ("title", "summary", "lexical", "vector_input_text"))

    def test_exact_projection_document_is_deterministic_and_json_native(self):
        projection = _projection()
        assert validate_capability_search_projection(projection) == projection
        first = build_capability_search_document(projection, _model(), _filters())
        second = build_capability_search_document(json.loads(json.dumps(projection)), _model(), _filters())
        assert first == second == validate_capability_search_document(json.loads(json.dumps(first)))
        assert first["candidate_only"] is True
        assert first["execution_authority"] is False
        assert "params" not in json.dumps(first)

    def test_empty_document_resources_mean_no_named_resource(self):
        filters = _filters()
        filters["resource_ids"] = []
        document = build_capability_search_document(_projection(), _model(), filters)
        assert document["filters"]["resource_ids"] == []

    def test_set_like_metadata_is_canonical_and_duplicates_are_rejected(self):
        projection = _projection()
        first_filters = _filters()
        first_filters.update(acl_principals=["principal-2", "principal-1"], resource_ids=["resource-2", "resource-1"])
        second_filters = copy.deepcopy(first_filters)
        second_filters.update(acl_principals=list(reversed(first_filters["acl_principals"])), resource_ids=list(reversed(first_filters["resource_ids"])))
        assert build_capability_search_document(projection, _model(), first_filters) == build_capability_search_document(projection, _model(), second_filters)
        first_filters["resource_ids"] = ["resource-1", "resource-1"]
        _assert_redacted(build_capability_search_document, projection, _model(), first_filters)

    @pytest.mark.parametrize("state", ["retired", "inactive", "incomplete", "draft_unapproved", "draft_unverified"])
    def test_every_coherent_negative_state_is_non_indexable(self, state):
        projection = _projection_for_state(state)
        assert capability_projection_is_indexable(projection) is False
        with pytest.raises(CapabilitySearchBoundaryError):
            build_capability_search_document(projection, _model(), _filters())

    @pytest.mark.parametrize("mutation", [
        lambda p: p.update(host_verified=False),
        lambda p: p.update(audit_visible=False),
        lambda p: p.update(autonomous_routable=False),
        lambda p: p.update(trust_state="inactive"),
        lambda p: p["semantic_ids"].update(intents=["z.intent", "a.intent"]),
    ])
    def test_incoherent_or_noncanonical_projection_is_rejected(self, mutation):
        projection = _projection()
        mutation(projection)
        _assert_redacted(validate_capability_search_projection, projection)

    @pytest.mark.parametrize("mutation", [
        lambda p: p.update(extra=True), lambda p: p.pop("title"),
        lambda p: p.update(active=1),
        lambda p: p.update(title="bad\u200btext"), lambda p: p.update(content_digest="no"),
        lambda p: p["semantic_ids"].update(extra=[]),
        lambda p: p["semantic_ids"].update(intents=["duplicate", "duplicate"]),
    ])
    def test_projection_refuses_unknown_malformed_and_abusive_data(self, mutation):
        projection = _projection()
        mutation(projection)
        with pytest.raises(CapabilitySearchBoundaryError) as caught:
            validate_capability_search_projection(projection)
        assert str(caught.value) == caught.value.code

    def test_document_tamper_and_tombstone_content_are_refused_or_bounded(self):
        document = build_capability_search_document(_projection(), _model(), _filters())
        tampered = copy.deepcopy(document)
        tampered["model"]["dimensions"] += 1
        with pytest.raises(CapabilitySearchBoundaryError):
            validate_capability_search_document(tampered)
        retired = _projection()
        retired.update(active=False, retired=True, trust_state="retired", autonomous_routable=False)
        tombstone = build_capability_search_tombstone(
            retired, "catalog.retired", prior_document_digest=document["document_digest"],
        )
        assert validate_capability_search_tombstone(json.loads(json.dumps(tombstone))) == tombstone
        encoded = json.dumps(tombstone)
        assert "lexical" not in encoded and "vector" not in encoded and "title" not in encoded

    def test_query_requires_prefilter_and_strict_bounds(self):
        filters = _filters()
        filters["resource_ids"] = []
        filters["capability_ids"] = []
        request = build_capability_search_request("extract document", 10, filters, _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64, page_size=5)
        assert request["retrieval_order"][:2] == ["hard_filter", "lexical"]
        assert request["prefilter_required"] is True
        for invalid in (True, "10", 0, 101):
            with pytest.raises(CapabilitySearchBoundaryError):
                build_capability_search_request("query", invalid, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)

    def test_cursor_roundtrip_tamper_and_cross_query_refusal(self):
        request = build_capability_search_request("query", 2, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        key = b"bounded-test-integrity-key"
        cursor = encode_capability_search_cursor(request, 900, "capability-1", key, emitted_count=1)
        assert decode_capability_search_cursor(cursor, request, key)["last_score"] == 900
        with pytest.raises(CapabilitySearchBoundaryError):
            decode_capability_search_cursor(cursor[:-1] + "0", request, key)
        other = build_capability_search_request("other", 2, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        with pytest.raises(CapabilitySearchBoundaryError):
            decode_capability_search_cursor(cursor, other, key)

    def test_non_null_request_cursor_requires_key_and_binds_forward_page(self):
        base = build_capability_search_request("query", 2, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        key = b"bounded-test-integrity-key"
        cursor = encode_capability_search_cursor(base, 700, "capability-b", key, emitted_count=1)
        _assert_redacted(build_capability_search_request, "query", 2, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64, 50, 50, None, cursor)
        paged = build_capability_search_request("query", 2, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64, cursor=cursor, integrity_key=key)
        _assert_redacted(validate_capability_search_request, paged)
        candidate = _bind_candidate({"tenant_id": "tenant-1", "space_id": "space-1", "capability_id": "capability-a", "status": "active", "acl_principals": ["principal-1"], "acl_scopes": ["scope.read"], "risk_classification": "low", "resource_ids": ["resource-1"], "score": 900, "source_projection_digest": "sha256:" + "e" * 64, "upstream_content_digest": "sha256:" + "a" * 64, "document_digest": "sha256:" + "f" * 64, "model_digest": _model()["model_digest"], "index_digest": paged["index_digest"], "snapshot_digest": paged["snapshot_digest"], "candidate_only": True, "execution_authority": False})
        page = {"page_version": "flyto.capability-search-page.v1", "request_digest": paged["request_digest"], "candidates": [candidate], "next_cursor": None, "candidate_only": True, "execution_authority": False}
        _assert_redacted(validate_capability_search_page, page, paged, key)

    def test_candidate_page_rejects_duplicate_unstable_and_filter_mismatch(self):
        request = build_capability_search_request("query", 2, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        candidate = _bind_candidate({"tenant_id": "tenant-1", "space_id": "space-1", "capability_id": "capability-1", "status": "active", "acl_principals": ["principal-1"], "acl_scopes": ["scope.read"], "risk_classification": "low", "resource_ids": ["resource-1"], "score": 900, "source_projection_digest": "sha256:" + "e" * 64, "upstream_content_digest": "sha256:" + "a" * 64, "document_digest": "sha256:" + "f" * 64, "model_digest": _model()["model_digest"], "index_digest": request["index_digest"], "snapshot_digest": request["snapshot_digest"], "candidate_only": True, "execution_authority": False})
        page = {"page_version": "flyto.capability-search-page.v1", "request_digest": request["request_digest"], "candidates": [candidate], "next_cursor": None, "candidate_only": True, "execution_authority": False}
        assert validate_capability_search_page(json.loads(json.dumps(page)), request) == page
        page["candidates"] = [candidate, candidate]
        with pytest.raises(CapabilitySearchBoundaryError):
            validate_capability_search_page(page, request)

    def test_request_rebuild_blocks_mutation_and_malformed_shapes(self):
        request = build_capability_search_request("query", 2, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        assert validate_capability_search_request(json.loads(json.dumps(request))) == request
        mutated = copy.deepcopy(request)
        mutated["hard_filters"]["tenant_id"] = "tenant-2"
        _assert_redacted(validate_capability_search_request, mutated)
        for malformed in ({}, {"request_digest": request["request_digest"]}, HostileMapping()):
            _assert_redacted(validate_capability_search_request, malformed)

    def test_unknown_capability_discovery_and_cursor_bound_page(self):
        filters = _filters()
        filters["capability_ids"] = []
        filters["resource_ids"] = []
        request = build_capability_search_request("query", 2, filters, _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        candidate = _bind_candidate({"tenant_id": "tenant-1", "space_id": "space-1", "capability_id": "previously-unknown", "status": "active", "acl_principals": ["principal-1"], "acl_scopes": ["scope.read"], "risk_classification": "low", "resource_ids": ["resource-new"], "score": 700, "source_projection_digest": "sha256:" + "e" * 64, "upstream_content_digest": "sha256:" + "a" * 64, "document_digest": "sha256:" + "f" * 64, "model_digest": _model()["model_digest"], "index_digest": request["index_digest"], "snapshot_digest": request["snapshot_digest"], "candidate_only": True, "execution_authority": False})
        key = b"bounded-test-integrity-key"
        cursor = encode_capability_search_cursor(request, 700, "previously-unknown", key, emitted_count=1)
        page = {"page_version": "flyto.capability-search-page.v1", "request_digest": request["request_digest"], "candidates": [candidate], "next_cursor": cursor, "candidate_only": True, "execution_authority": False}
        assert validate_capability_search_page(page, request, key)["candidates"] == [candidate]
        page["next_cursor"] = encode_capability_search_cursor(request, 701, "previously-unknown", key, emitted_count=1)
        _assert_redacted(validate_capability_search_page, page, request, key)

    def test_cursor_cumulative_count_exhausts_top_k(self):
        key = b"bounded-test-integrity-key"
        filters = _filters()
        filters["capability_ids"] = []
        base = build_capability_search_request("query", 2, filters, _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64, page_size=1)
        first_candidate = _candidate(base, "capability-a", 900)
        first_cursor = encode_capability_search_cursor(base, 900, "capability-a", key, emitted_count=1)
        first_page = {"page_version": "flyto.capability-search-page.v1", "request_digest": base["request_digest"], "candidates": [first_candidate], "next_cursor": first_cursor, "candidate_only": True, "execution_authority": False}
        assert validate_capability_search_page(first_page, base, key)["next_cursor"] == first_cursor
        second = build_capability_search_request("query", 2, filters, _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64, page_size=1, cursor=first_cursor, integrity_key=key)
        second_candidate = _candidate(second, "capability-b", 800)
        exhausted = encode_capability_search_cursor(second, 800, "capability-b", key, emitted_count=2)
        second_page = {"page_version": "flyto.capability-search-page.v1", "request_digest": second["request_digest"], "candidates": [second_candidate], "next_cursor": None, "candidate_only": True, "execution_authority": False}
        assert validate_capability_search_page(second_page, second, key)["next_cursor"] is None
        _assert_redacted(build_capability_search_request, "query", 2, filters, _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64, 50, 50, 1, exhausted, key)
        second_page["next_cursor"] = exhausted
        _assert_redacted(validate_capability_search_page, second_page, second, key)
        wrong_count = encode_capability_search_cursor(second, 800, "capability-b", key, emitted_count=1)
        second_page["next_cursor"] = wrong_count
        _assert_redacted(validate_capability_search_page, second_page, second, key)

    def test_maximum_100_candidate_page_fits_boundary_budget(self):
        filters = _filters()
        filters["capability_ids"] = []
        request = build_capability_search_request("query", 100, filters, _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64, page_size=100)
        candidates = [_candidate(request, "capability-{:03d}".format(index), 1000 - index) for index in range(100)]
        page = {"page_version": "flyto.capability-search-page.v1", "request_digest": request["request_digest"], "candidates": candidates, "next_cursor": None, "candidate_only": True, "execution_authority": False}
        assert len(validate_capability_search_page(page, request)["candidates"]) == 100
        oversized = copy.deepcopy(page)
        oversized["candidates"].append(_candidate(request, "capability-100", 900))
        _assert_redacted(validate_capability_search_page, oversized, request)

    def test_candidate_digest_model_snapshot_and_risk_ceiling_binding(self):
        request = build_capability_search_request("query", 1, _filters(), _model(), "sha256:" + "c" * 64, "sha256:" + "d" * 64)
        base = _bind_candidate({"tenant_id": "tenant-1", "space_id": "space-1", "capability_id": "capability-1", "status": "active", "acl_principals": ["principal-1"], "acl_scopes": ["scope.read"], "risk_classification": "critical", "resource_ids": ["resource-1"], "score": 1, "source_projection_digest": "sha256:" + "e" * 64, "upstream_content_digest": "sha256:" + "a" * 64, "document_digest": "sha256:" + "f" * 64, "model_digest": _model()["model_digest"], "index_digest": request["index_digest"], "snapshot_digest": request["snapshot_digest"], "candidate_only": True, "execution_authority": False})
        page = {"page_version": "flyto.capability-search-page.v1", "request_digest": request["request_digest"], "candidates": [base], "next_cursor": None, "candidate_only": True, "execution_authority": False}
        _assert_redacted(validate_capability_search_page, page, request)
        for field in ("model_digest", "index_digest", "snapshot_digest", "document_digest"):
            tampered = copy.deepcopy(page)
            tampered["candidates"][0].update(risk_classification="low")
            tampered["candidates"][0][field] = "sha256:" + "0" * 64
            _assert_redacted(validate_capability_search_page, tampered, request)


class TestListAndSearch:

    def test_builtins_always_present(self, engine):
        ids = [b["id"] for b in engine.list_blueprints()]
        assert "browser_scrape" in ids
        assert "api_get" in ids

    def test_learned_sorted_by_score_desc(self, engine):
        engine.learn_from_workflow(make_workflow(tag="low_score"), name="low")
        r2 = engine.learn_from_workflow(make_workflow_alt(), name="high")
        engine._blueprints[r2["data"]["id"]]["score"] = 90

        learned = [b for b in engine.list_blueprints() if b.get("source") == "learned"]
        scores = [b["score"] for b in learned]
        assert scores == sorted(scores, reverse=True)

    def test_search_returns_builtins(self, engine):
        results = engine.search("screenshot")
        ids = [b["id"] for b in results]
        assert "browser_screenshot" in ids

    def test_search_empty_returns_all(self, engine):
        assert len(engine.search("")) == len(engine.list_blueprints())

    def test_search_by_tag(self, engine):
        results = engine.search("api")
        ids = [b["id"] for b in results]
        assert "api_get" in ids

    def test_search_by_name(self, engine):
        results = engine.search("Login")
        ids = [b["id"] for b in results]
        assert "browser_login" in ids

    def test_search_no_match(self, engine):
        results = engine.search("xyznonexistent")
        assert len(results) == 0

    def test_summary_has_required_fields(self, engine):
        results = engine.list_blueprints()
        for bp in results:
            assert "id" in bp
            assert "name" in bp
            assert "description" in bp
            assert "tags" in bp
            assert "module_ids" in bp
            assert "args" in bp

    def test_summary_exposes_module_ids_without_step_parameters(self, engine):
        learned = engine.learn_from_workflow(
            make_workflow(tag="module_summary"),
            name="module_summary",
        )
        summary = next(
            bp
            for bp in engine.list_blueprints()
            if bp["id"] == learned["data"]["id"]
        )

        assert summary["module_ids"] == [
            "math.add",
            "string.reverse",
            "array.sort",
        ]
        assert "steps" not in summary
        assert "params" not in summary

    def test_learned_summary_exposes_trust_and_community_confidence(self, engine):
        learned = engine.learn_from_workflow(
            make_workflow(tag="summary_trust"),
            name="summary_trust",
        )
        bp_id = learned["data"]["id"]
        engine.report_outcome(
            bp_id,
            success=True,
            execution_id="community-summary-1",
            evidence_tier="community",
        )

        summary = next(bp for bp in engine.list_blueprints() if bp["id"] == bp_id)

        assert summary["trust_tier"] == "community"
        assert summary["community_observations"] == 1
        assert summary["effective_score"] == summary["score"]

    def test_search_matches_repository_compatibility(self, engine):
        learned = engine.learn_from_execution(
            make_workflow(tag="repo_context"),
            name="generic_endpoint",
            compatibility={
                "repository": "flytohub/payments-api",
                "framework": "fastapi",
            },
        )

        results = engine.search("payments-api")

        assert learned["data"]["id"] in [bp["id"] for bp in results]

    def test_summary_exposes_evidence_card(self, engine):
        learned = engine.learn_from_workflow(
            make_workflow(tag="evidence_summary"),
            name="evidence_summary",
        )
        bp_id = learned["data"]["id"]
        engine.report_outcome(
            bp_id,
            success=True,
            execution_id="summary-evidence-1",
            evidence={
                "duration_ms": 42,
                "model_calls_used": 0,
                "planner_model_calls_used": 0,
                "model_call_scope": "planner",
                "selection_mode": "deterministic",
            },
        )

        summary = next(bp for bp in engine.list_blueprints() if bp["id"] == bp_id)

        assert summary["evidence_card"]["sample_count"] == 1
        assert summary["evidence_card"]["zero_planner_model_call_count"] == 1
        assert summary["evidence_card"]["zero_llm_reuse_count"] == 1

    def test_community_signal_influences_ranking_without_rewriting_score(self, engine):
        low = engine.learn_from_workflow(
            make_workflow(tag="community_low"),
            name="community_low",
        )
        high = engine.learn_from_workflow(
            make_workflow_alt(),
            name="community_high",
        )
        low_id = low["data"]["id"]
        high_id = high["data"]["id"]

        for index in range(20):
            engine.report_outcome(
                high_id,
                success=True,
                execution_id="community-rank-{}".format(index),
                evidence_tier="community",
            )

        learned = [bp for bp in engine.list_blueprints() if bp.get("source") == "learned"]
        ids = [bp["id"] for bp in learned]
        assert ids.index(high_id) < ids.index(low_id)
        assert engine._blueprints[high_id]["score"] == 50

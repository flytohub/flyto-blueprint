# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Intent-based blueprint matcher — system-level routing that replaces prompt reliance.

Three matching layers (cascading fallback):
1. Embedding similarity (semantic, highest quality)
2. Keyword BM25 (fast, no API call)
3. Tag word-match (existing, baseline)

Usage:
    matcher = IntentMatcher(blueprints)
    await matcher.build_index(api_key="sk-...")      # one-time, cached
    results = await matcher.match("scrape prices from amazon")
    # → [{"id": "browser_scrape", "score": 0.92, "method": "embedding"}, ...]
"""
import hashlib
import hmac
import json
import logging
import math
import os
import struct
import base64
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CAPABILITY_SEARCH_VERSION = "flyto.capability-search.v1"
CAPABILITY_CARD_VERSION = "flyto.capability-card.v1"
CAPABILITY_DOCUMENT_VERSION = "flyto.capability-search-document.v1"
CAPABILITY_MUTATION_VERSION = "flyto.capability-search-mutation.v1"
CAPABILITY_TOMBSTONE_VERSION = "flyto.capability-search-tombstone.v1"
CAPABILITY_QUERY_VERSION = "flyto.capability-search-query.v1"
CAPABILITY_PAGE_VERSION = "flyto.capability-search-page.v1"
CAPABILITY_CURSOR_VERSION = "flyto.capability-search-cursor.v1"


class CapabilitySearchBoundaryError(ValueError):
    """Stable content-free rejection at the capability-search trust boundary."""

    def __init__(self, code: str = "CAPABILITY_SEARCH_INVALID") -> None:
        super().__init__(code)
        self.code = code


_PROJECTION_FIELDS = frozenset({
    "search_version", "card_version", "tenant_id", "space_id", "capability_id",
    "content_digest", "semantic_origin", "source_kind", "title", "summary",
    "semantic_ids", "approved", "host_verified", "verified", "active", "retired",
    "complete", "trust_state", "autonomous_routable", "audit_visible",
})
_SEMANTIC_FIELDS = frozenset({"intents", "affordances", "effects", "events"})
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]*$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_ORIGINS = frozenset({"declared", "static_derived"})
_SAFE_TRUST_STATES = frozenset({
    "approved_verified", "retired", "inactive", "incomplete",
    "draft_unapproved", "draft_unverified",
})
_INDEXABLE_TRUST_STATE = "approved_verified"
_RISK_LEVELS = ("minimal", "low", "medium", "high", "critical")
_MAX_JSON_BYTES = 32768
_MAX_PROJECTION_BYTES = 65536
_MAX_REQUEST_BYTES = 131072
_MAX_DOCUMENT_BYTES = 196608
_MAX_PAGE_BYTES = 524288
_MAX_TEXT = 2048
_MAX_LIST = 64
_MAX_ACL = 128
_MAX_DEPTH = 8
_MAX_NODES = 512
_MAX_DOCUMENT_NODES = 2048
_MAX_REQUEST_NODES = 2048
_MAX_PAGE_NODES = 8192
_MAX_SAFE_INTEGER = 9007199254740991


def _reject(code: str = "CAPABILITY_SEARCH_INVALID") -> None:
    raise CapabilitySearchBoundaryError(code)


def _snapshot_json(value: Any, *, max_nodes: int = _MAX_NODES, max_bytes: int = _MAX_JSON_BYTES) -> Any:
    """Detach recursively bounded exact JSON while redacting hostile faults."""
    nodes = 0

    def visit(item: Any, depth: int) -> Any:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes or depth > _MAX_DEPTH:
            _reject()
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            if not -_MAX_SAFE_INTEGER <= item <= _MAX_SAFE_INTEGER:
                _reject()
            return item
        if type(item) is str:
            return item
        if isinstance(item, Mapping):
            keys = list(item.keys())
            if len(keys) > max_nodes or any(type(key) is not str for key in keys):
                _reject()
            if len(keys) != len(set(keys)):
                _reject()
            return {key: visit(item[key], depth + 1) for key in keys}
        if isinstance(item, list):
            if len(item) > max_nodes:
                _reject()
            return [visit(child, depth + 1) for child in item]
        _reject()

    try:
        detached = visit(value, 0)
        _canonical_json(detached, max_bytes=max_bytes)
        return detached
    except CapabilitySearchBoundaryError:
        raise
    except BaseException:
        _reject()


def _plain_mapping(value: Any, fields: frozenset[str], *, max_nodes: int = _MAX_NODES, max_bytes: int = _MAX_JSON_BYTES) -> dict:
    data = _snapshot_json(value, max_nodes=max_nodes, max_bytes=max_bytes)
    if type(data) is not dict or set(data) != fields:
        _reject()
    return data


def _text(value: Any, *, identifier: bool = False, maximum: Optional[int] = None, empty: bool = False) -> str:
    limit = 128 if identifier and maximum is None else (_MAX_TEXT if maximum is None else maximum)
    if type(value) is not str or (not value and not empty) or len(value) > limit:
        _reject()
    if value != unicodedata.normalize("NFC", value) or value != value.strip():
        _reject()
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs", "Co", "Cn"} for char in value):
        _reject()
    if identifier and not _ID_RE.fullmatch(value):
        _reject()
    return value


def _projection_text(value: Any) -> str:
    """Validate producer-canonical display text without trimming it."""
    if type(value) is not str or len(value) > 2000 or value != unicodedata.normalize("NFC", value):
        _reject()
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value):
        _reject()
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        _reject()
    return value


def _boolean(value: Any) -> bool:
    if type(value) is not bool:
        _reject()
    return value


def _integer(value: Any, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _reject()
    return value


def _string_list(value: Any, *, maximum: int = _MAX_LIST, identifier_maximum: int = 128, canonical: bool = False) -> list[str]:
    value = _snapshot_json(value)
    if type(value) is not list or len(value) > maximum:
        _reject()
    result = [_text(item, identifier=True, maximum=identifier_maximum) for item in value]
    if len(result) != len(set(result)):
        _reject()
    return sorted(result) if canonical else result


def _canonical_json(value: Any, *, max_bytes: int = _MAX_JSON_BYTES) -> bytes:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except Exception:
        _reject()
    if len(encoded) > max_bytes:
        _reject()
    return encoded


def _sha(value: Any, *, max_bytes: int = _MAX_JSON_BYTES) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value, max_bytes=max_bytes)).hexdigest()


def validate_capability_search_projection(value: Any) -> dict:
    """Return the exact safe projection or reject it without echoing content."""
    data = _plain_mapping(value, _PROJECTION_FIELDS, max_bytes=_MAX_PROJECTION_BYTES)
    if data["search_version"] != CAPABILITY_SEARCH_VERSION or data["card_version"] != CAPABILITY_CARD_VERSION:
        _reject()
    for field in ("tenant_id", "space_id", "capability_id"):
        data[field] = _text(data[field], identifier=True, maximum=192)
    data["content_digest"] = _digest(data["content_digest"])
    data["semantic_origin"] = _text(data["semantic_origin"], identifier=True, maximum=192)
    if data["source_kind"] is not None:
        data["source_kind"] = _text(data["source_kind"], identifier=True, maximum=192)
    if data["semantic_origin"] not in _SAFE_ORIGINS:
        _reject()
    data["title"] = _projection_text(data["title"])
    data["summary"] = _projection_text(data["summary"])
    semantic = _plain_mapping(data["semantic_ids"], _SEMANTIC_FIELDS)
    data["semantic_ids"] = {name: _string_list(semantic[name], maximum=32, identifier_maximum=192) for name in sorted(_SEMANTIC_FIELDS)}
    if any(items != sorted(items) for items in data["semantic_ids"].values()):
        _reject()
    for field in ("approved", "host_verified", "verified", "active", "retired", "complete", "autonomous_routable", "audit_visible"):
        data[field] = _boolean(data[field])
    data["trust_state"] = _text(data["trust_state"], identifier=True)
    has_complete_content = (
        data["source_kind"] is not None
        and bool(data["title"].strip())
        and bool(data["summary"].strip())
        and any(data["semantic_ids"].values())
    )
    expected_routable = all((data["complete"], data["approved"], data["verified"], data["active"])) and not data["retired"]
    if data["retired"]:
        expected_state = "retired"
    elif not data["active"]:
        expected_state = "inactive"
    elif not data["complete"]:
        expected_state = "incomplete"
    elif not data["approved"]:
        expected_state = "draft_unapproved"
    elif not data["verified"]:
        expected_state = "draft_unverified"
    else:
        expected_state = _INDEXABLE_TRUST_STATE
    if (
        data["trust_state"] not in _SAFE_TRUST_STATES
        or data["host_verified"] is not True
        or data["audit_visible"] is not True
        or data["trust_state"] != expected_state
        or data["autonomous_routable"] != expected_routable
        or (data["complete"] and not has_complete_content)
    ):
        _reject()
    _canonical_json(data, max_bytes=_MAX_PROJECTION_BYTES)
    return data


def capability_projection_is_indexable(value: Any) -> bool:
    """Report eligibility; validation failures still reject instead of becoming false."""
    data = validate_capability_search_projection(value)
    return all((
        data["approved"], data["host_verified"], data["verified"],
        data["active"], data["complete"], data["autonomous_routable"],
        data["audit_visible"], data["source_kind"] is not None,
        bool(data["title"].strip()), bool(data["summary"].strip()),
        any(data["semantic_ids"].values()),
    )) and not data["retired"] and data["trust_state"] == _INDEXABLE_TRUST_STATE


def _validate_model(value: Any) -> dict:
    fields = frozenset({"model_id", "model_version", "dimensions", "model_digest"})
    data = _plain_mapping(value, fields, max_nodes=_MAX_REQUEST_NODES, max_bytes=_MAX_REQUEST_BYTES)
    data["model_id"] = _text(data["model_id"], identifier=True)
    data["model_version"] = _text(data["model_version"], identifier=True)
    data["dimensions"] = _integer(data["dimensions"], 1, 65536)
    data["model_digest"] = _digest(data["model_digest"])
    return data


def _validate_filters(value: Any, tenant_id: str, space_id: str, *, document: bool = False) -> dict:
    fields = frozenset({"tenant_id", "space_id", "status", "acl_principals", "acl_scopes", "risk_classification", "resource_ids", "capability_ids"})
    data = _plain_mapping(value, fields, max_nodes=_MAX_REQUEST_NODES, max_bytes=_MAX_REQUEST_BYTES)
    data["tenant_id"] = _text(data["tenant_id"], identifier=True, maximum=192)
    data["space_id"] = _text(data["space_id"], identifier=True, maximum=192)
    if data["tenant_id"] != tenant_id or data["space_id"] != space_id:
        _reject()
    data["status"] = _text(data["status"], identifier=True)
    if data["status"] != "active":
        _reject()
    for field in ("acl_principals", "acl_scopes", "resource_ids", "capability_ids"):
        identifier_maximum = 192 if field == "capability_ids" else 128
        data[field] = _string_list(data[field], maximum=_MAX_ACL, identifier_maximum=identifier_maximum, canonical=True)
        if field in {"acl_principals", "acl_scopes"} and not data[field]:
            _reject()
    data["risk_classification"] = _text(data["risk_classification"], identifier=True)
    if data["risk_classification"] not in _RISK_LEVELS:
        _reject()
    if document and len(data["capability_ids"]) != 1:
        _reject()
    return data


def build_capability_search_document(projection: Any, model: Any, filters: Any) -> dict:
    """Build a deterministic JSON-native document without computing a vector."""
    source = validate_capability_search_projection(projection)
    if not capability_projection_is_indexable(source):
        _reject("CAPABILITY_SEARCH_NOT_INDEXABLE")
    model_data = _validate_model(model)
    filter_data = _validate_filters(filters, source["tenant_id"], source["space_id"], document=True)
    if filter_data["capability_ids"] != [source["capability_id"]]:
        _reject()
    lexical = {
        "title": source["title"], "summary": source["summary"],
        "intents": source["semantic_ids"]["intents"],
        "affordances": source["semantic_ids"]["affordances"],
        "effects": source["semantic_ids"]["effects"], "events": source["semantic_ids"]["events"],
    }
    vector_input = "\n".join([source["title"], source["summary"]] + [item for name in sorted(_SEMANTIC_FIELDS) for item in source["semantic_ids"][name]])
    document = {
        "document_version": CAPABILITY_DOCUMENT_VERSION,
        "source_projection": source,
        "source_projection_digest": _sha(source, max_bytes=_MAX_PROJECTION_BYTES),
        "upstream_content_digest": source["content_digest"],
        "model": model_data, "filters": filter_data, "lexical": lexical,
        "vector_input_text": vector_input, "candidate_only": True,
        "execution_authority": False,
    }
    document["document_digest"] = _sha(document, max_bytes=_MAX_DOCUMENT_BYTES)
    return document


def validate_capability_search_document(value: Any) -> dict:
    """Rebuild and compare every derived field and digest on document read."""
    fields = frozenset({"document_version", "source_projection", "source_projection_digest", "upstream_content_digest", "model", "filters", "lexical", "vector_input_text", "candidate_only", "execution_authority", "document_digest"})
    data = _plain_mapping(value, fields, max_nodes=_MAX_DOCUMENT_NODES, max_bytes=_MAX_DOCUMENT_BYTES)
    if data["document_version"] != CAPABILITY_DOCUMENT_VERSION or data["candidate_only"] is not True or data["execution_authority"] is not False:
        _reject()
    rebuilt = build_capability_search_document(data["source_projection"], data["model"], data["filters"])
    if not hmac.compare_digest(
        _canonical_json(data, max_bytes=_MAX_DOCUMENT_BYTES),
        _canonical_json(rebuilt, max_bytes=_MAX_DOCUMENT_BYTES),
    ):
        _reject("CAPABILITY_SEARCH_TAMPERED")
    return rebuilt


def build_capability_search_mutation(document: Any, operation: str = "upsert") -> dict:
    """Build an exact deterministic upsert mutation."""
    if type(operation) is not str or operation != "upsert":
        _reject()
    doc = validate_capability_search_document(document)
    mutation = {"mutation_version": CAPABILITY_MUTATION_VERSION, "operation": operation, "document": doc}
    mutation["mutation_digest"] = _sha(mutation, max_bytes=_MAX_DOCUMENT_BYTES)
    return mutation


def validate_capability_search_mutation(value: Any) -> dict:
    """Validate an upsert mutation and its document on read."""
    fields = frozenset({"mutation_version", "operation", "document", "mutation_digest"})
    data = _plain_mapping(value, fields, max_nodes=_MAX_DOCUMENT_NODES, max_bytes=_MAX_DOCUMENT_BYTES)
    if data["mutation_version"] != CAPABILITY_MUTATION_VERSION or data["operation"] != "upsert":
        _reject()
    rebuilt = build_capability_search_mutation(data["document"])
    if not hmac.compare_digest(
        _canonical_json(data, max_bytes=_MAX_DOCUMENT_BYTES),
        _canonical_json(rebuilt, max_bytes=_MAX_DOCUMENT_BYTES),
    ):
        _reject("CAPABILITY_SEARCH_TAMPERED")
    return rebuilt


_TOMBSTONE_IDENTITY_FIELDS = frozenset({
    "tenant_id", "space_id", "capability_id", "source_projection_digest",
    "upstream_content_digest", "document_digest",
})


def build_capability_search_tombstone(source: Any, reason: str, operation: str = "retire", prior_document_digest: Optional[str] = None) -> dict:
    """Build a content-free tombstone from ineligible source or prior identity."""
    if type(operation) is not str or operation not in {"retire", "delete"}:
        _reject()
    detached = _snapshot_json(source)
    if type(detached) is not dict:
        _reject()
    if set(detached) == _PROJECTION_FIELDS:
        projection = validate_capability_search_projection(detached)
        if capability_projection_is_indexable(projection):
            _reject("CAPABILITY_SEARCH_STILL_INDEXABLE")
        identity = {
            "tenant_id": projection["tenant_id"], "space_id": projection["space_id"],
            "capability_id": projection["capability_id"],
            "source_projection_digest": _sha(projection, max_bytes=_MAX_PROJECTION_BYTES),
            "upstream_content_digest": projection["content_digest"],
            "document_digest": _digest(prior_document_digest),
        }
    else:
        identity = _plain_mapping(detached, _TOMBSTONE_IDENTITY_FIELDS)
        for field in ("tenant_id", "space_id", "capability_id"):
            identity[field] = _text(identity[field], identifier=True, maximum=192)
        for field in ("source_projection_digest", "upstream_content_digest", "document_digest"):
            identity[field] = _digest(identity[field])
    tombstone = {
        "tombstone_version": CAPABILITY_TOMBSTONE_VERSION, "operation": operation,
        **identity,
        "reason": _text(reason, identifier=True, maximum=128), "retired": True,
    }
    tombstone["tombstone_digest"] = _sha(tombstone)
    return tombstone


def validate_capability_search_tombstone(value: Any) -> dict:
    """Validate a bounded tombstone without requiring retained search content."""
    fields = frozenset({"tombstone_version", "operation", "tenant_id", "space_id", "capability_id", "source_projection_digest", "upstream_content_digest", "document_digest", "reason", "retired", "tombstone_digest"})
    data = _plain_mapping(value, fields)
    if data["tombstone_version"] != CAPABILITY_TOMBSTONE_VERSION or data["operation"] not in {"retire", "delete"} or data["retired"] is not True:
        _reject()
    for field in ("tenant_id", "space_id", "capability_id"):
        _text(data[field], identifier=True, maximum=192)
    for field in ("source_projection_digest", "upstream_content_digest", "document_digest"):
        _digest(data[field])
    _text(data["reason"], identifier=True, maximum=128)
    claimed = _digest(data["tombstone_digest"])
    expected = _sha({key: item for key, item in data.items() if key != "tombstone_digest"})
    if not hmac.compare_digest(claimed, expected):
        _reject("CAPABILITY_SEARCH_TAMPERED")
    return data


_REQUEST_FIELDS = frozenset({
    "request_version", "query", "top_k", "page_size", "hard_filters",
    "prefilter_required", "retrieval_order", "model", "index_digest",
    "snapshot_digest", "weights", "cursor", "request_digest",
})


def build_capability_search_request(query: str, top_k: int, filters: Any, model: Any, index_digest: str, snapshot_digest: str, lexical_weight: int = 50, vector_weight: int = 50, page_size: Optional[int] = None, cursor: Optional[str] = None, integrity_key: Optional[bytes] = None) -> dict:
    """Build a backend-neutral request whose hard filters precede retrieval."""
    query = _text(query, maximum=2048)
    top_k = _integer(top_k, 1, 100)
    size = top_k if page_size is None else _integer(page_size, 1, 100)
    if size > top_k:
        _reject()
    raw_filters = _plain_mapping(
        filters,
        frozenset({"tenant_id", "space_id", "status", "acl_principals", "acl_scopes", "risk_classification", "resource_ids", "capability_ids"}),
        max_nodes=_MAX_REQUEST_NODES,
        max_bytes=_MAX_REQUEST_BYTES,
    )
    tenant = _text(raw_filters["tenant_id"], identifier=True, maximum=192)
    space = _text(raw_filters["space_id"], identifier=True, maximum=192)
    clean_filters = _validate_filters(raw_filters, tenant, space)
    request = {
        "request_version": CAPABILITY_QUERY_VERSION, "query": query, "top_k": top_k,
        "page_size": size, "hard_filters": clean_filters, "prefilter_required": True,
        "retrieval_order": ["hard_filter", "lexical", "ann", "fuse"],
        "model": _validate_model(model), "index_digest": _digest(index_digest),
        "snapshot_digest": _digest(snapshot_digest),
        "weights": {"lexical": _integer(lexical_weight, 0, 100), "vector": _integer(vector_weight, 0, 100)},
        "cursor": cursor,
    }
    if lexical_weight + vector_weight != 100 or (cursor is not None and integrity_key is None):
        _reject()
    request["request_digest"] = _sha(
        {key: value for key, value in request.items() if key != "cursor"},
        max_bytes=_MAX_REQUEST_BYTES,
    )
    if cursor is not None:
        continuation = decode_capability_search_cursor(cursor, {**request, "cursor": None}, integrity_key)
        if continuation["emitted_count"] >= top_k:
            _reject("CAPABILITY_SEARCH_CURSOR_INVALID")
    return request


def validate_capability_search_request(value: Any, integrity_key: Optional[bytes] = None) -> dict:
    """Detach and rebuild every request field before cursor or page use."""
    data = _plain_mapping(value, _REQUEST_FIELDS, max_nodes=_MAX_REQUEST_NODES, max_bytes=_MAX_REQUEST_BYTES)
    if data["request_version"] != CAPABILITY_QUERY_VERSION:
        _reject()
    filters = data["hard_filters"]
    if type(filters) is not dict:
        _reject()
    rebuilt = build_capability_search_request(
        data["query"], data["top_k"], filters, data["model"],
        data["index_digest"], data["snapshot_digest"],
        lexical_weight=_plain_mapping(data["weights"], frozenset({"lexical", "vector"}))["lexical"],
        vector_weight=data["weights"]["vector"], page_size=data["page_size"],
        cursor=data["cursor"], integrity_key=integrity_key,
    )
    if data["prefilter_required"] is not True or data["retrieval_order"] != ["hard_filter", "lexical", "ann", "fuse"]:
        _reject()
    if not hmac.compare_digest(
        _canonical_json(data, max_bytes=_MAX_REQUEST_BYTES),
        _canonical_json(rebuilt, max_bytes=_MAX_REQUEST_BYTES),
    ):
        _reject("CAPABILITY_SEARCH_TAMPERED")
    return rebuilt


def encode_capability_search_cursor(request: Any, last_score: int, last_capability_id: str, integrity_key: bytes, emitted_count: int) -> str:
    """Create a versioned opaque keyset cursor bound to the complete request."""
    if type(integrity_key) is not bytes or len(integrity_key) < 16:
        _reject()
    clean_request = validate_capability_search_request(request, integrity_key)
    body = {
        "cursor_version": CAPABILITY_CURSOR_VERSION,
        "request_digest": clean_request["request_digest"],
        "last_score": _integer(last_score, -1000000000, 1000000000),
        "last_capability_id": _text(last_capability_id, identifier=True, maximum=192),
        "emitted_count": _integer(emitted_count, 1, clean_request["top_k"]),
    }
    payload = base64.urlsafe_b64encode(_canonical_json(body)).rstrip(b"=")
    signature = hmac.new(integrity_key, payload, hashlib.sha256).hexdigest().encode("ascii")
    return (payload + b"." + signature).decode("ascii")


def decode_capability_search_cursor(cursor: str, request: Any, integrity_key: bytes) -> dict:
    """Verify cursor integrity and reject cross-request reuse."""
    if type(cursor) is not str or len(cursor) > 4096 or type(integrity_key) is not bytes or len(integrity_key) < 16:
        _reject()
    detached_request = _plain_mapping(
        request, _REQUEST_FIELDS, max_nodes=_MAX_REQUEST_NODES, max_bytes=_MAX_REQUEST_BYTES,
    )
    clean_request = validate_capability_search_request({**detached_request, "cursor": None})
    try:
        payload, signature = cursor.encode("ascii").split(b".", 1)
        expected = hmac.new(integrity_key, payload, hashlib.sha256).hexdigest().encode("ascii")
        if not hmac.compare_digest(signature, expected):
            _reject("CAPABILITY_SEARCH_CURSOR_INVALID")
        decoded = base64.urlsafe_b64decode(payload + b"=" * (-len(payload) % 4))
        body = _snapshot_json(json.loads(decoded))
    except CapabilitySearchBoundaryError:
        raise
    except Exception:
        _reject("CAPABILITY_SEARCH_CURSOR_INVALID")
    body = _plain_mapping(body, frozenset({"cursor_version", "request_digest", "last_score", "last_capability_id", "emitted_count"}))
    if body["cursor_version"] != CAPABILITY_CURSOR_VERSION or body["request_digest"] != clean_request["request_digest"]:
        _reject("CAPABILITY_SEARCH_CURSOR_INVALID")
    _digest(body["request_digest"])
    _integer(body["last_score"], -1000000000, 1000000000)
    _text(body["last_capability_id"], identifier=True, maximum=192)
    _integer(body["emitted_count"], 1, clean_request["top_k"])
    return body


def validate_capability_search_page(value: Any, request: Any, integrity_key: Optional[bytes] = None) -> dict:
    """Validate a deterministically ordered candidate-only backend page."""
    fields = frozenset({"page_version", "request_digest", "candidates", "next_cursor", "candidate_only", "execution_authority"})
    clean_request = validate_capability_search_request(request, integrity_key)
    page = _plain_mapping(value, fields, max_nodes=_MAX_PAGE_NODES, max_bytes=_MAX_PAGE_BYTES)
    if page["page_version"] != CAPABILITY_PAGE_VERSION or page["request_digest"] != clean_request["request_digest"] or page["candidate_only"] is not True or page["execution_authority"] is not False:
        _reject()
    candidates = page["candidates"]
    prior = None
    emitted_before = 0
    if clean_request["cursor"] is not None:
        prior = decode_capability_search_cursor(clean_request["cursor"], clean_request, integrity_key)
        emitted_before = prior["emitted_count"]
        if emitted_before >= clean_request["top_k"]:
            _reject("CAPABILITY_SEARCH_CURSOR_INVALID")
    if type(candidates) is not list or len(candidates) > clean_request["page_size"] or len(candidates) > clean_request["top_k"] - emitted_before:
        _reject()
    expected_fields = frozenset({"tenant_id", "space_id", "capability_id", "status", "acl_principals", "acl_scopes", "risk_classification", "resource_ids", "score", "source_projection_digest", "upstream_content_digest", "document_digest", "model_digest", "index_digest", "snapshot_digest", "candidate_digest", "candidate_only", "execution_authority"})
    cleaned, seen, previous = [], set(), None
    hard = clean_request["hard_filters"]
    for raw in candidates:
        item = _plain_mapping(raw, expected_fields, max_nodes=_MAX_PAGE_NODES, max_bytes=_MAX_PAGE_BYTES)
        capability_id = _text(item["capability_id"], identifier=True, maximum=192)
        score = _integer(item["score"], -1000000000, 1000000000)
        key = (-score, capability_id)
        if capability_id in seen or (previous is not None and key <= previous):
            _reject()
        seen.add(capability_id)
        previous = key
        item["tenant_id"] = _text(item["tenant_id"], identifier=True, maximum=192)
        item["space_id"] = _text(item["space_id"], identifier=True, maximum=192)
        item["status"] = _text(item["status"], identifier=True)
        for field in ("tenant_id", "space_id", "status"):
            if item[field] != hard[field]:
                _reject()
        for field in ("acl_principals", "acl_scopes"):
            item[field] = _string_list(item[field], maximum=_MAX_ACL, canonical=True)
            if not set(hard[field]).issubset(item[field]):
                _reject()
        item["risk_classification"] = _text(item["risk_classification"], identifier=True)
        if item["risk_classification"] not in _RISK_LEVELS or _RISK_LEVELS.index(item["risk_classification"]) > _RISK_LEVELS.index(hard["risk_classification"]):
            _reject()
        item["resource_ids"] = _string_list(item["resource_ids"], maximum=_MAX_ACL, canonical=True)
        if hard["resource_ids"] and not set(hard["resource_ids"]).issubset(item["resource_ids"]):
            _reject()
        if hard["capability_ids"] and capability_id not in hard["capability_ids"]:
            _reject()
        for field in ("source_projection_digest", "upstream_content_digest", "document_digest", "model_digest", "index_digest", "snapshot_digest"):
            item[field] = _digest(item[field])
        claimed_candidate_digest = _digest(item["candidate_digest"])
        expected_candidate_digest = _sha(
            {field: content for field, content in item.items() if field != "candidate_digest"},
            max_bytes=_MAX_PAGE_BYTES,
        )
        if not hmac.compare_digest(claimed_candidate_digest, expected_candidate_digest):
            _reject("CAPABILITY_SEARCH_TAMPERED")
        if item["model_digest"] != clean_request["model"]["model_digest"] or item["index_digest"] != clean_request["index_digest"] or item["snapshot_digest"] != clean_request["snapshot_digest"]:
            _reject()
        if item["candidate_only"] is not True or item["execution_authority"] is not False:
            _reject()
        cleaned.append(item)
    if prior is not None:
        prior_key = (-prior["last_score"], prior["last_capability_id"])
        if any((-item["score"], item["capability_id"]) <= prior_key for item in cleaned):
            _reject("CAPABILITY_SEARCH_CURSOR_INVALID")
    if page["next_cursor"] is not None:
        if not cleaned or integrity_key is None:
            _reject()
        cursor = decode_capability_search_cursor(page["next_cursor"], clean_request, integrity_key)
        last = cleaned[-1]
        emitted_after = emitted_before + len(cleaned)
        if emitted_after >= clean_request["top_k"] or cursor["last_score"] != last["score"] or cursor["last_capability_id"] != last["capability_id"] or cursor["emitted_count"] != emitted_after:
            _reject("CAPABILITY_SEARCH_CURSOR_INVALID")
    page["candidates"] = cleaned
    return page

# Cache dir for embedding vectors
_CACHE_DIR = Path(os.environ.get("FLYTO_CACHE_DIR", Path.home() / ".flyto")) / "bp_embeddings"

# Synonym expansion for keyword matching
SYNONYMS: Dict[str, List[str]] = {
    "scrape": ["extract", "crawl", "fetch", "get", "pull"],
    "screenshot": ["capture", "snap", "photo", "image"],
    "download": ["fetch", "get", "save", "retrieve"],
    "fill": ["type", "input", "enter", "write", "submit"],
    "send": ["post", "notify", "dispatch", "push", "deliver"],
    "login": ["auth", "signin", "sign-in", "authenticate", "log-in", "signon"],
    "convert": ["transform", "parse", "export", "change"],
    "compress": ["optimize", "reduce", "shrink", "minify"],
    "resize": ["scale", "dimension", "crop"],
    "search": ["find", "query", "lookup", "google"],
    "monitor": ["check", "health", "ping", "uptime", "status"],
    "pdf": ["document", "print", "export"],
    "email": ["mail", "smtp", "inbox"],
    "slack": ["notification", "webhook", "alert", "message"],
    "csv": ["spreadsheet", "excel", "table", "data"],
    "json": ["api", "data", "parse", "response"],
    "ocr": ["text", "recognize", "read", "scan"],
    "performance": ["speed", "vitals", "audit", "lighthouse"],
    "responsive": ["mobile", "tablet", "desktop", "breakpoint"],
}

# Reverse synonym map: "crawl" → ["scrape"]
_REVERSE_SYNONYMS: Dict[str, List[str]] = {}
for _canonical, _aliases in SYNONYMS.items():
    for _alias in _aliases:
        _REVERSE_SYNONYMS.setdefault(_alias, []).append(_canonical)
    _REVERSE_SYNONYMS.setdefault(_canonical, []).extend(_aliases)


def expand_query(query: str) -> List[str]:
    """Expand query words with synonyms. Returns unique expanded word list."""
    words = query.lower().split()
    expanded = set(words)
    for word in words:
        if word in _REVERSE_SYNONYMS:
            expanded.update(_REVERSE_SYNONYMS[word])
        if word in SYNONYMS:
            expanded.update(SYNONYMS[word])
    return list(expanded)


def _pack_vector(vec: List[float]) -> bytes:
    """Serialize a float list to compact binary (4 bytes per float)."""
    return struct.pack("{}f".format(len(vec)), *vec)


def _unpack_vector(data: bytes) -> List[float]:
    """Deserialize binary data back to a list of floats."""
    n = len(data) // 4
    return list(struct.unpack("{}f".format(n), data))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _bp_text(bp: dict) -> str:
    """Build searchable text from blueprint metadata."""
    parts = [
        bp.get("name", ""),
        bp.get("description", ""),
        " ".join(bp.get("tags", [])),
        bp.get("id", "").replace("_", " "),
    ]
    return " ".join(parts)


def _score_candidate(
    words: List[str],
    tags: List[str],
    id_words: List[str],
    name_words: List[str],
    desc: str,
) -> float:
    """Score how well *words* match a single blueprint's metadata.

    Weights: exact tag 3.0, id word 2.0, name word 1.5,
    partial tag substring 1.0, description substring 0.5.
    """
    score = 0.0
    all_bp_words = set(tags + name_words + id_words)
    for word in words:
        if word in all_bp_words:
            if word in tags:
                score += 3.0
            elif word in id_words:
                score += 2.0
            elif word in name_words:
                score += 1.5
        elif any(word in t for t in tags):
            score += 1.0
        elif word in desc:
            score += 0.5
    return score


class IntentMatcher:
    """System-level blueprint matcher with embedding + keyword + tag fallback."""

    def __init__(self, blueprints: Dict[str, dict]) -> None:
        """Initialize the matcher with a dict of blueprint_id to blueprint data."""
        self._blueprints = blueprints
        self._embeddings: Dict[str, List[float]] = {}  # bp_id → vector
        self._index_built = False

    async def build_index(self, api_key: Optional[str] = None) -> bool:
        """Build embedding index for all blueprints. Cached to disk."""
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.info("No API key — embedding index skipped, using keyword-only")
            return False

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Check cache freshness: hash of blueprint IDs
        bp_ids = sorted(self._blueprints.keys())
        cache_hash = hashlib.md5(json.dumps(bp_ids).encode()).hexdigest()[:12]
        cache_file = _CACHE_DIR / "index_{}.json".format(cache_hash)

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached = json.load(f)
                self._embeddings = {k: v for k, v in cached.items() if k in self._blueprints}
                self._index_built = True
                logger.info("Loaded cached embedding index (%d vectors)", len(self._embeddings))
                return True
            except Exception as e:
                logger.debug("Cache load failed: %s", e)

        # Build embeddings via OpenAI API
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)

            texts = []
            ids = []
            for bp_id, bp in self._blueprints.items():
                if bp.get("retired"):
                    continue
                texts.append(_bp_text(bp))
                ids.append(bp_id)

            # Batch embed (max 2048 per call)
            all_embeddings = []
            for i in range(0, len(texts), 100):
                batch = texts[i:i + 100]
                resp = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=batch,
                )
                for item in resp.data:
                    all_embeddings.append(item.embedding)

            for bp_id, vec in zip(ids, all_embeddings):
                self._embeddings[bp_id] = vec

            # Cache to disk
            with open(cache_file, "w") as f:
                json.dump(self._embeddings, f)

            self._index_built = True
            logger.info("Built embedding index (%d vectors)", len(self._embeddings))
            return True

        except Exception as e:
            logger.warning("Embedding index build failed: %s", e)
            return False

    async def match(
        self,
        query: str,
        api_key: Optional[str] = None,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Match user intent to blueprints. Returns ranked results.

        Cascading strategy:
        1. If embedding index exists → semantic similarity
        2. Always → keyword BM25 with synonym expansion
        3. Merge and deduplicate
        """
        results: Dict[str, Dict[str, Any]] = {}

        # Layer 1: Embedding similarity
        if self._index_built and self._embeddings:
            try:
                emb_results = await self._match_embedding(query, api_key, top_k, threshold)
                for r in emb_results:
                    results[r["id"]] = r
            except Exception as e:
                logger.debug("Embedding match failed: %s", e)

        # Layer 2: Keyword matching with synonym expansion
        kw_results = self._match_keywords(query, top_k)
        for r in kw_results:
            if r["id"] in results:
                # Boost score if both methods agree
                results[r["id"]]["score"] = max(results[r["id"]]["score"], r["score"])
                results[r["id"]]["method"] = "both"
            else:
                results[r["id"]] = r

        # Sort by score descending
        ranked = sorted(results.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    async def _match_embedding(
        self, query: str, api_key: Optional[str], top_k: int, threshold: float,
    ) -> List[Dict[str, Any]]:
        """Semantic matching via embedding cosine similarity."""
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return []

        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=[query],
        )
        query_vec = resp.data[0].embedding

        scored = []
        for bp_id, bp_vec in self._embeddings.items():
            sim = _cosine_similarity(query_vec, bp_vec)
            if sim >= threshold:
                scored.append({"id": bp_id, "score": sim, "method": "embedding"})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _match_keywords(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Keyword matching with synonym expansion and BM25-like scoring."""
        expanded = expand_query(query)
        original_words = query.lower().split()
        scored = []

        for bp_id, bp in self._blueprints.items():
            if bp.get("retired"):
                continue

            tags = [t.lower() for t in bp.get("tags", [])]
            name_words = bp.get("name", "").lower().split()
            desc = bp.get("description", "").lower()
            id_words = bp_id.lower().replace("_", " ").split()

            score = _score_candidate(
                expanded, tags, id_words, name_words, desc,
            )

            # Coverage bonus: what % of original query words matched?
            all_bp_words = set(tags + name_words + id_words)
            if original_words:
                original_hits = sum(
                    1 for w in original_words
                    if w in all_bp_words or any(w in t for t in all_bp_words)
                )
                coverage = original_hits / len(original_words)
                score *= (0.5 + coverage * 0.5)

            # Quality bonus for learned blueprints
            if bp.get("_source") == "learned":
                score += bp.get("score", 50) / 200.0

            if score > 0:
                normalized = min(1.0, score / 15.0)
                scored.append({"id": bp_id, "score": normalized, "method": "keyword"})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


# ---------------------------------------------------------------------------
# Query → Blueprint mapping tracker (for evolution learning)
# ---------------------------------------------------------------------------

class QueryTracker:
    """Track query → blueprint mappings for learning which blueprints users prefer.

    Stores in SQLite for persistence. Used to:
    1. Boost frequently-used blueprints in search results
    2. Train better intent classifiers over time
    3. Detect gaps (queries with no blueprint match)
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the tracker with an optional SQLite database path."""
        self._db_path = db_path or str(
            Path(os.environ.get("FLYTO_CACHE_DIR", Path.home() / ".flyto")) / "query_tracker.db"
        )
        self._initialized = False

    async def init(self) -> None:
        """Create the SQLite tables if they do not already exist."""
        if self._initialized:
            return
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS query_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    blueprint_id TEXT NOT NULL,
                    success INTEGER DEFAULT 0,
                    timestamp REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS query_gaps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_qm_query ON query_map(query)"
            )
            await db.commit()
        self._initialized = True

    async def record_match(self, query: str, blueprint_id: str, success: bool) -> None:
        """Record that a query was matched to a blueprint."""
        await self.init()
        import time
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO query_map (query, blueprint_id, success, timestamp) VALUES (?, ?, ?, ?)",
                (query.lower().strip(), blueprint_id, int(success), time.time()),
            )
            await db.commit()

    async def record_gap(self, query: str) -> None:
        """Record a query that had no blueprint match — identifies coverage gaps."""
        await self.init()
        import time
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO query_gaps (query, timestamp) VALUES (?, ?)",
                (query.lower().strip(), time.time()),
            )
            await db.commit()

    async def get_popular_mappings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most popular query→blueprint mappings for training data."""
        await self.init()
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("""
                SELECT query, blueprint_id, COUNT(*) as count,
                       SUM(success) as successes
                FROM query_map
                GROUP BY query, blueprint_id
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            return [
                {"query": r[0], "blueprint_id": r[1], "count": r[2], "successes": r[3]}
                for r in rows
            ]

    async def get_gaps(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get queries with no blueprint match — candidates for new blueprints."""
        await self.init()
        import aiosqlite
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("""
                SELECT query, COUNT(*) as count
                FROM query_gaps
                GROUP BY query
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            return [{"query": r[0], "count": r[1]} for r in rows]

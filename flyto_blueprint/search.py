# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Blueprint listing and search with relevance+quality blending."""
from typing import Dict, List


def bp_summary(bp: dict) -> dict:
    """Build a summary dict for a blueprint."""
    summary = {
        "id": bp["id"],
        "name": bp.get("name", ""),
        "description": bp.get("description", ""),
        "tags": bp.get("tags", []),
        "args": {
            name: {
                "type": meta.get("type", "string"),
                "required": meta.get("required", False),
                "description": meta.get("description", ""),
            }
            for name, meta in bp.get("args", {}).items()
        },
    }
    if bp.get("_source") == "learned":
        summary["source"] = "learned"
        summary["score"] = max(0, min(100, bp.get("score", 50)))
        summary["use_count"] = bp.get("use_count", 0)
    return summary


def list_blueprints(blueprints: Dict[str, dict]) -> List[dict]:
    """Return summaries of all non-retired blueprints, sorted by score desc.

    Builtins are treated as score=50 so they don't permanently dominate.
    """
    results = []
    for bp in blueprints.values():
        if bp.get("retired"):
            continue
        results.append(bp)
    results.sort(key=lambda b: max(0, min(100, b.get("score", 50))), reverse=True)
    return [bp_summary(bp) for bp in results]


def search_blueprints(query: str, blueprints: Dict[str, dict]) -> List[dict]:
    """Search blueprints by matching query against tags, name, and description.

    Results are weighted by text relevance + blueprint quality score.
    Returns all non-retired blueprints if query is empty.
    """
    if not query:
        return list_blueprints(blueprints)

    query_lower = query.lower()
    scored = []

    for bp in blueprints.values():
        if bp.get("retired"):
            continue

        relevance = 0
        name = bp.get("name", "").lower()
        desc = bp.get("description", "").lower()
        tags = [t.lower() for t in bp.get("tags", [])]

        # Tag exact match gets highest score
        for tag in tags:
            if tag in query_lower or query_lower in tag:
                relevance += 3

        # Name match
        if query_lower in name:
            relevance += 2

        # Description match
        if query_lower in desc:
            relevance += 1

        if relevance > 0:
            quality_bonus = bp.get("score", 50) / 100.0 if bp.get("_source") == "learned" else 1.0
            final_score = relevance + quality_bonus
            scored.append((final_score, bp))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [bp_summary(bp) for _, bp in scored]

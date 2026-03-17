# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Blueprint listing and search with relevance+quality blending + synonym expansion."""
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
    """Return summaries of all non-retired blueprints, sorted by score desc."""
    results = []
    for bp in blueprints.values():
        if bp.get("retired"):
            continue
        results.append(bp)
    results.sort(key=lambda b: max(0, min(100, b.get("score", 50))), reverse=True)
    return [bp_summary(bp) for bp in results]


def search_blueprints(query: str, blueprints: Dict[str, dict]) -> List[dict]:
    """Search blueprints with two-pass scoring: exact words first, synonym fallback.

    Pass 1: Score using original query words (high confidence).
    Pass 2: If top score < threshold, boost with synonym-expanded words (lower weight).
    """
    if not query:
        return list_blueprints(blueprints)

    query_lower = query.lower()
    query_words = [w for w in query_lower.split() if len(w) > 1]

    # Get synonym expansions (only the NEW words, not originals)
    synonym_words: List[str] = []
    try:
        from flyto_blueprint.intent import expand_query
        all_expanded = expand_query(query)
        synonym_words = [w for w in all_expanded if w not in query_words]
    except Exception:
        pass

    scored = []

    for bp in blueprints.values():
        if bp.get("retired"):
            continue

        score = _score_blueprint(query_words, synonym_words, bp)
        if score > 0:
            scored.append((score, bp))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [bp_summary(bp) for _, bp in scored]


def _score_blueprint(
    query_words: List[str], synonym_words: List[str], bp: dict,
) -> float:
    """Score a single blueprint against query words and synonym expansions.

    Two-pass scoring:
    - Pass 1: original query words at full weight.
    - Pass 2: synonym words at half weight (only when pass 1 has gaps).

    Returns 0.0 when there are no matches (caller should skip the blueprint).
    """
    name = bp.get("name", "").lower()
    desc = bp.get("description", "").lower()
    tags = [t.lower() for t in bp.get("tags", [])]
    id_words = bp.get("id", "").lower().replace("_", " ").split()

    score = 0.0

    # --- Pass 1: Original words (full weight) ---
    original_hits = 0
    for word in query_words:
        if word in tags:
            score += 4.0
            original_hits += 1
        elif word in id_words:
            score += 3.0
            original_hits += 1
        elif word in name.split():
            score += 2.0
            original_hits += 1
        elif any(word in t for t in tags):
            score += 1.5
            original_hits += 1
        elif word in desc:
            score += 0.5
            original_hits += 1

    # All-words bonus
    if original_hits == len(query_words) and len(query_words) > 1:
        score += 3.0

    # --- Pass 2: Synonym words (half weight, only if original didn't fully match) ---
    if original_hits < len(query_words) and synonym_words:
        for word in synonym_words:
            if word in tags:
                score += 1.5
            elif word in id_words:
                score += 1.0
            elif any(word in t for t in tags):
                score += 0.5

    # Quality bonus for learned blueprints
    if score > 0:
        if bp.get("_source") == "learned":
            score += bp.get("score", 50) / 100.0
        else:
            score += 1.0  # builtins get baseline bonus

    return score

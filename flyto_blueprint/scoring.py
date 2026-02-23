# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Blueprint scoring: outcome reporting, boosting, use tracking, auto-retire."""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from flyto_blueprint.storage.base import StorageBackend

logger = logging.getLogger(__name__)

_RECENT_REPORTS_MAX = 200


def report_outcome(
    blueprint_id: str,
    success: bool,
    blueprints: Dict[str, dict],
    storage: Optional[StorageBackend] = None,
    execution_id: str = "",
    recent_reports: Optional[Dict[str, float]] = None,
) -> dict:
    """Report whether a blueprint-generated workflow succeeded or failed.

    Success: +5 (cap 100). Failure: -10 (floor 0). Auto-retire if score < 10.

    The in-memory *blueprints* dict is the source of truth; changes are
    persisted to *storage* afterwards on a best-effort basis.
    """
    # Dedup
    if execution_id and recent_reports is not None:
        if execution_id in recent_reports:
            return {"ok": True, "blueprint_id": blueprint_id, "skipped": "already_reported"}
        recent_reports[execution_id] = time.time()
        if len(recent_reports) > _RECENT_REPORTS_MAX:
            cutoff = time.time() - 3600
            stale = [k for k, v in recent_reports.items() if v <= cutoff]
            for k in stale:
                del recent_reports[k]

    bp = blueprints.get(blueprint_id)
    if not bp:
        return {"ok": False, "error": "Blueprint '{}' not found".format(blueprint_id)}

    # Compute new values from in-memory state
    old_score = bp.get("score", 50)
    if success:
        new_score = min(100, old_score + 5)
        bp["success_count"] = bp.get("success_count", 0) + 1
    else:
        new_score = max(0, old_score - 10)
        bp["fail_count"] = bp.get("fail_count", 0) + 1

    bp["score"] = new_score
    retired = new_score < 10
    if retired:
        bp["retired"] = True
        logger.info("Blueprint '%s' auto-retired (score=%d)", blueprint_id, new_score)

    # Best-effort persist to storage
    if storage is not None:
        try:
            storage.update(blueprint_id, {
                "score": new_score,
                "success_count": bp.get("success_count", 0),
                "fail_count": bp.get("fail_count", 0),
                "retired": retired,
            })
        except Exception:
            pass

    return {
        "ok": True,
        "blueprint_id": blueprint_id,
        "score": new_score,
        "success_count": bp.get("success_count", 0),
        "fail_count": bp.get("fail_count", 0),
        "retired": retired,
    }


def boost_score(
    blueprint_id: str,
    delta: int,
    blueprints: Dict[str, dict],
    storage: Optional[StorageBackend] = None,
) -> None:
    """Increase a blueprint's score by *delta* (clamped 0–100)."""
    bp = blueprints.get(blueprint_id)
    if not bp:
        return
    bp["score"] = min(100, max(0, bp.get("score", 50) + delta))
    if storage is not None:
        try:
            storage.update(blueprint_id, {"score": bp["score"]})
        except Exception:
            pass


def record_use(
    blueprint_id: str,
    blueprints: Dict[str, dict],
    storage: Optional[StorageBackend] = None,
) -> None:
    """Record that a blueprint was used (expand).

    Only tracks count — no score change. Score should only change from
    verified outcomes.
    """
    bp = blueprints.get(blueprint_id)
    if not bp:
        return
    bp["use_count"] = bp.get("use_count", 0) + 1
    now = datetime.now(timezone.utc).isoformat()
    bp["last_used_at"] = now
    if storage is not None:
        try:
            storage.update(blueprint_id, {
                "use_count": bp["use_count"],
                "last_used_at": now,
            })
        except Exception:
            pass

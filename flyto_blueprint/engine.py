# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""BlueprintEngine — orchestrator for loading, searching, expanding, and evolving blueprints."""
import logging
import time
from typing import Dict, List, Optional

from flyto_blueprint.compose import expand_blueprint
from flyto_blueprint.learn import learn_from_workflow as _learn
from flyto_blueprint.loader import load_blocks, load_builtins
from flyto_blueprint.scoring import boost_score, record_use, report_outcome
from flyto_blueprint.search import list_blueprints as _list, search_blueprints as _search
from flyto_blueprint.storage.base import StorageBackend
from flyto_blueprint.validate import validate_steps

logger = logging.getLogger(__name__)

_LEARNED_CACHE_TTL = 60  # seconds


class BlueprintEngine:
    """High-level orchestrator that wires together all blueprint subsystems.

    Parameters
    ----------
    storage : StorageBackend, optional
        Where to persist learned blueprints.  When *None*, the engine runs
        in builtin-only mode (no persistence for learned blueprints).
    """

    def __init__(self, storage: Optional[StorageBackend] = None) -> None:
        self._storage = storage
        self._blueprints: Dict[str, dict] = {}
        self._blocks: Dict[str, dict] = {}
        self._last_learned_refresh: float = 0.0
        self._recent_reports: Dict[str, float] = {}
        self._load_all()

    # ── Loading ────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        self._blocks = load_blocks()
        self._blueprints = load_builtins()
        self._load_learned()
        logger.info("Loaded %d blueprints", len(self._blueprints))

    def _load_learned(self) -> None:
        """Load learned blueprints from storage (skip retired)."""
        if self._storage is None:
            return
        try:
            fresh: Dict[str, dict] = {}
            for bp in self._storage.load_all():
                if bp and isinstance(bp, dict) and "id" in bp:
                    if bp.get("retired"):
                        continue
                    bp["_source"] = "learned"
                    fresh[bp["id"]] = bp
            # Swap: remove old learned, add fresh
            stale_ids = [
                bp_id for bp_id, bp in self._blueprints.items()
                if bp.get("_source") == "learned"
            ]
            for bp_id in stale_ids:
                del self._blueprints[bp_id]
            self._blueprints.update(fresh)
            self._last_learned_refresh = time.time()
            logger.info("Loaded %d learned blueprints", len(fresh))
        except Exception as e:
            logger.warning("Failed to load learned blueprints: %s", e)

    def _maybe_refresh_learned(self) -> None:
        if time.time() - self._last_learned_refresh > _LEARNED_CACHE_TTL:
            self._load_learned()

    # ── Public API ─────────────────────────────────────────────────────

    def list_blueprints(self) -> List[dict]:
        """Return summaries of all non-retired blueprints, sorted by score desc."""
        self._maybe_refresh_learned()
        return _list(self._blueprints)

    def search(self, query: str) -> List[dict]:
        """Search blueprints by query. Empty query returns all."""
        self._maybe_refresh_learned()
        return _search(query, self._blueprints)

    def expand(self, blueprint_id: str, args: dict) -> dict:
        """Expand a blueprint with args. Returns ``{ok, data, warnings?}``."""
        self._maybe_refresh_learned()
        bp = self._blueprints.get(blueprint_id)
        if not bp and self._storage is not None:
            # Fallback: single-doc fetch
            loaded = self._storage.load_one(blueprint_id)
            if loaded and not loaded.get("retired"):
                loaded["_source"] = "learned"
                self._blueprints[loaded["id"]] = loaded
                bp = loaded
        if not bp:
            return {"ok": False, "error": "Blueprint '{}' not found".format(blueprint_id)}

        if bp.get("_source") == "learned":
            record_use(blueprint_id, self._blueprints, self._storage)

        result = expand_blueprint(bp, args, self._blocks)

        if result.get("ok"):
            warnings = validate_steps(result["data"]["steps"])
            if warnings:
                result["warnings"] = warnings

        return result

    def learn_from_workflow(
        self,
        workflow: dict,
        blueprint_id: Optional[str] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        verified: bool = False,
    ) -> dict:
        """Abstract a workflow into a reusable blueprint. Persists to storage."""
        result = _learn(
            workflow, self._blueprints, self._blocks,
            blueprint_id=blueprint_id, name=name, tags=tags, verified=verified,
        )
        if not result.get("ok"):
            return result

        # Dedup boost
        if result.get("action") == "boosted_existing":
            boost_score(result["blueprint_id"], 3, self._blueprints, self._storage)
            return result

        bp = result["data"]
        # Persist
        if self._storage is not None:
            save_bp = {k: v for k, v in bp.items() if not k.startswith("_")}
            try:
                self._storage.save(bp["id"], save_bp)
            except Exception as e:
                logger.warning("Failed to persist blueprint: %s", e)
                return {"ok": False, "error": "Failed to save: {}".format(e)}

        # Register in memory
        self._blueprints[bp["id"]] = bp
        from flyto_blueprint.search import bp_summary
        return {"ok": True, "data": bp_summary(bp)}

    def learn_from_execution(
        self,
        workflow: dict,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """Learn from a successful execution (verified, initial score 70)."""
        return self.learn_from_workflow(
            workflow=workflow, name=name, tags=tags, verified=True,
        )

    def report_outcome(
        self,
        blueprint_id: str,
        success: bool,
        execution_id: str = "",
    ) -> dict:
        """Report outcome for a blueprint."""
        return report_outcome(
            blueprint_id, success, self._blueprints,
            self._storage, execution_id, self._recent_reports,
        )

# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""BlueprintEngine — orchestrator for loading, searching, expanding, and evolving blueprints."""
import logging
import time
from typing import Dict, List, Mapping, Optional

from flyto_blueprint.compose import expand_blueprint
from flyto_blueprint.learn import learn_from_workflow as _learn
from flyto_blueprint.loader import load_blocks, load_builtins
from flyto_blueprint.scoring import boost_score, record_use, report_outcome
from flyto_blueprint.search import list_blueprints as _list, search_blueprints as _search
from flyto_blueprint.sharing import (
    SigningKey,
    blueprint_definition_digest,
    export_blueprint_bundle,
    import_blueprint_bundle,
)
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
        """Initialize the engine with an optional storage backend and load all blueprints."""
        self._storage = storage
        self._blueprints: Dict[str, dict] = {}
        self._blocks: Dict[str, dict] = {}
        self._last_learned_refresh: float = 0.0
        self._recent_reports: Dict[str, float] = {}
        self._load_all()

    # ── Loading ────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        """Load builtin blueprints, compose blocks, and learned blueprints."""
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
        """Reload learned blueprints from storage if the TTL has expired."""
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
        compatibility: Optional[dict] = None,
        verification: Optional[dict] = None,
        trust_tier: Optional[str] = None,
    ) -> dict:
        """Abstract a workflow into a reusable blueprint. Persists to storage."""
        result = _learn(
            workflow, self._blueprints, self._blocks,
            blueprint_id=blueprint_id, name=name, tags=tags, verified=verified,
            compatibility=compatibility, verification=verification,
            trust_tier=trust_tier,
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
        compatibility: Optional[dict] = None,
        verification: Optional[dict] = None,
    ) -> dict:
        """Learn from a successful execution (verified, initial score 70)."""
        return self.learn_from_workflow(
            workflow=workflow,
            name=name,
            tags=tags,
            verified=True,
            compatibility=compatibility,
            verification=verification,
            trust_tier="local_verified",
        )

    def report_outcome(
        self,
        blueprint_id: str,
        success: bool,
        execution_id: str = "",
        evidence_tier: str = "local_verified",
        evidence: Optional[dict] = None,
    ) -> dict:
        """Report an outcome and optional allowlisted execution evidence."""
        return report_outcome(
            blueprint_id, success, self._blueprints,
            self._storage, execution_id, self._recent_reports,
            evidence_tier=evidence_tier,
            evidence=evidence,
        )

    def export_blueprint(
        self,
        blueprint_id: str,
        *,
        publisher: str = "",
        claimed_tier: Optional[str] = None,
        evidence: Optional[dict] = None,
        signing_key: Optional[SigningKey] = None,
    ) -> dict:
        """Create an integrity-checked portable bundle without uploading it."""
        self._maybe_refresh_learned()
        blueprint = self._blueprints.get(blueprint_id)
        if not blueprint:
            return {"ok": False, "error": "Blueprint '{}' not found".format(blueprint_id)}
        return export_blueprint_bundle(
            blueprint,
            publisher=publisher,
            claimed_tier=claimed_tier,
            evidence=evidence,
            signing_key=signing_key,
        )

    def import_blueprint(
        self,
        bundle: dict,
        *,
        trusted_keys: Optional[Mapping[str, SigningKey]] = None,
    ) -> dict:
        """Validate and persist a portable bundle with trust quarantine."""
        result = import_blueprint_bundle(bundle, trusted_keys=trusted_keys)
        if not result.get("ok"):
            return result

        imported = result["data"]
        incoming_digest = blueprint_definition_digest(imported)
        for existing in self._blueprints.values():
            if blueprint_definition_digest(existing) == incoming_digest:
                from flyto_blueprint.search import bp_summary
                return {
                    "ok": True,
                    "action": "already_present",
                    "data": bp_summary(existing),
                    "trust_tier": existing.get("trust_tier", "community"),
                }

        original_id = imported["id"]
        if original_id in self._blueprints:
            suffix = incoming_digest.removeprefix("sha256:")[:8]
            candidate = "{}_shared_{}".format(original_id, suffix)
            counter = 1
            while candidate in self._blueprints:
                counter += 1
                candidate = "{}_shared_{}_{}".format(original_id, suffix, counter)
            imported["id"] = candidate

        imported["_source"] = "learned"
        warnings = validate_steps(imported.get("steps", []))
        if self._storage is not None:
            save_blueprint = {
                key: value
                for key, value in imported.items()
                if not key.startswith("_")
            }
            try:
                self._storage.save(imported["id"], save_blueprint)
            except Exception as error:
                logger.warning("Failed to persist imported blueprint: %s", error)
                return {"ok": False, "error": "Failed to save: {}".format(error)}

        self._blueprints[imported["id"]] = imported
        from flyto_blueprint.search import bp_summary
        response = {
            "ok": True,
            "action": "imported",
            "data": bp_summary(imported),
            "trust_tier": imported["trust_tier"],
            "signature_verified": result["signature_verified"],
        }
        if warnings:
            response["warnings"] = warnings
        return response

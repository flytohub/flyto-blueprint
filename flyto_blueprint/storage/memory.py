# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""In-memory storage backend for tests and ephemeral use."""
import copy
from typing import Callable, Dict, List, Optional

from flyto_blueprint.storage.base import StorageBackend


class MemoryBackend(StorageBackend):
    """Stores blueprints in a plain dict. Data is lost on process exit."""

    def __init__(self) -> None:
        """Initialize with an empty in-memory dict."""
        self._data: Dict[str, dict] = {}

    def load_all(self) -> List[dict]:
        """Return deep copies of all stored blueprints."""
        return [copy.deepcopy(v) for v in self._data.values()]

    def save(self, blueprint_id: str, data: dict) -> None:
        """Store a deep copy of *data* under *blueprint_id*."""
        self._data[blueprint_id] = copy.deepcopy(data)

    def update(self, blueprint_id: str, fields: dict) -> None:
        """Merge *fields* into the stored blueprint if it exists."""
        if blueprint_id in self._data:
            self._data[blueprint_id].update(fields)

    def load_one(self, blueprint_id: str) -> Optional[dict]:
        """Return a deep copy of a single blueprint, or None."""
        data = self._data.get(blueprint_id)
        return copy.deepcopy(data) if data is not None else None

    def delete(self, blueprint_id: str) -> None:
        """Remove the blueprint if it exists; no-op otherwise."""
        self._data.pop(blueprint_id, None)

    def atomic_update(
        self,
        blueprint_id: str,
        update_fn: Callable[[dict], Optional[dict]],
    ) -> Optional[dict]:
        """Apply *update_fn* in-place and return a deep copy of the result."""
        data = self._data.get(blueprint_id)
        if data is None:
            return None
        result = update_fn(data)
        if result is not None:
            self._data[blueprint_id] = result
        return copy.deepcopy(result) if result is not None else None

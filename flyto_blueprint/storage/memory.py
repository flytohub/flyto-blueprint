# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""In-memory storage backend for tests and ephemeral use."""
import copy
from typing import Callable, Dict, List, Optional

from flyto_blueprint.storage.base import StorageBackend


class MemoryBackend(StorageBackend):
    """Stores blueprints in a plain dict. Data is lost on process exit."""

    def __init__(self) -> None:
        self._data: Dict[str, dict] = {}

    def load_all(self) -> List[dict]:
        return [copy.deepcopy(v) for v in self._data.values()]

    def save(self, blueprint_id: str, data: dict) -> None:
        self._data[blueprint_id] = copy.deepcopy(data)

    def update(self, blueprint_id: str, fields: dict) -> None:
        if blueprint_id in self._data:
            self._data[blueprint_id].update(fields)

    def load_one(self, blueprint_id: str) -> Optional[dict]:
        data = self._data.get(blueprint_id)
        return copy.deepcopy(data) if data is not None else None

    def delete(self, blueprint_id: str) -> None:
        self._data.pop(blueprint_id, None)

    def atomic_update(
        self,
        blueprint_id: str,
        update_fn: Callable[[dict], Optional[dict]],
    ) -> Optional[dict]:
        data = self._data.get(blueprint_id)
        if data is None:
            return None
        result = update_fn(data)
        if result is not None:
            self._data[blueprint_id] = result
        return copy.deepcopy(result) if result is not None else None

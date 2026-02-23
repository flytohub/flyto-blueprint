# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Abstract storage backend for blueprints."""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


class StorageBackend(ABC):
    """Abstract base class for blueprint persistence."""

    @abstractmethod
    def load_all(self) -> List[dict]:
        """Load all stored blueprints. Returns list of raw dicts."""

    @abstractmethod
    def save(self, blueprint_id: str, data: dict) -> None:
        """Save or overwrite a blueprint."""

    @abstractmethod
    def update(self, blueprint_id: str, fields: dict) -> None:
        """Update specific fields of a blueprint."""

    @abstractmethod
    def load_one(self, blueprint_id: str) -> Optional[dict]:
        """Load a single blueprint by ID. Returns None if not found."""

    @abstractmethod
    def delete(self, blueprint_id: str) -> None:
        """Delete a blueprint by ID."""

    def atomic_update(
        self,
        blueprint_id: str,
        update_fn: Callable[[dict], Optional[dict]],
    ) -> Optional[dict]:
        """Read-modify-write a blueprint atomically.

        The update_fn receives the current data dict and returns the
        updated dict, or None to abort. Default implementation is
        non-atomic (load + save); backends can override for true
        atomicity (e.g. Firestore transactions).
        """
        data = self.load_one(blueprint_id)
        if data is None:
            return None
        result = update_fn(data)
        if result is not None:
            self.save(blueprint_id, result)
        return result

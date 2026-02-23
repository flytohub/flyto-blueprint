# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""flyto-blueprint — Self-evolving workflow pattern engine."""
from flyto_blueprint.engine import BlueprintEngine
from flyto_blueprint.storage.base import StorageBackend
from flyto_blueprint.storage.memory import MemoryBackend

__all__ = ["BlueprintEngine", "StorageBackend", "MemoryBackend", "get_engine"]

_engine = None


def get_engine(storage: StorageBackend = None) -> BlueprintEngine:
    """Get or create the default BlueprintEngine singleton.

    On first call, *storage* sets the backend. Subsequent calls
    return the same instance regardless of the *storage* argument.
    """
    global _engine
    if _engine is None:
        _engine = BlueprintEngine(storage=storage)
    return _engine

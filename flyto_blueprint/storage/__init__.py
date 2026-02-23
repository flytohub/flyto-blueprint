# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
from flyto_blueprint.storage.base import StorageBackend
from flyto_blueprint.storage.memory import MemoryBackend

__all__ = ["StorageBackend", "MemoryBackend"]

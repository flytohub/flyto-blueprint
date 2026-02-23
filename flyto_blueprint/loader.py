# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""YAML loader for builtin blueprints and compose blocks."""
import logging
from pathlib import Path
from typing import Dict

import yaml

logger = logging.getLogger(__name__)

_BLUEPRINTS_DIR = Path(__file__).parent / "blueprints"
_BLOCKS_DIR = _BLUEPRINTS_DIR / "blocks"


def load_builtins() -> Dict[str, dict]:
    """Load all builtin blueprint YAML files.

    Returns a dict mapping blueprint ID → blueprint dict.
    Each blueprint gets ``_source = "builtin"`` added.
    """
    blueprints: Dict[str, dict] = {}
    if not _BLUEPRINTS_DIR.is_dir():
        logger.warning("Blueprints directory not found: %s", _BLUEPRINTS_DIR)
        return blueprints

    for path in _BLUEPRINTS_DIR.glob("*.yaml"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                bp = yaml.safe_load(f)
            if bp and isinstance(bp, dict) and "id" in bp:
                bp["_source"] = "builtin"
                blueprints[bp["id"]] = bp
                logger.debug("Loaded blueprint: %s", bp["id"])
        except Exception as e:
            logger.warning("Failed to load blueprint %s: %s", path.name, e)

    return blueprints


def load_blocks() -> Dict[str, dict]:
    """Load all compose block YAML files.

    Returns a dict mapping block ID → block dict.
    """
    blocks: Dict[str, dict] = {}
    if not _BLOCKS_DIR.is_dir():
        return blocks

    for path in _BLOCKS_DIR.glob("*.yaml"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                block = yaml.safe_load(f)
            if block and isinstance(block, dict) and "id" in block:
                blocks[block["id"]] = block
                logger.debug("Loaded block: %s", block["id"])
        except Exception as e:
            logger.warning("Failed to load block %s: %s", path.name, e)

    logger.info("Loaded %d blocks", len(blocks))
    return blocks

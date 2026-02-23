# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Pydantic models for blueprints."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BlueprintArg(BaseModel):
    """Definition of a blueprint argument."""
    type: str = "string"
    required: bool = False
    description: str = ""


class Blueprint(BaseModel):
    """Full blueprint document."""
    id: str
    name: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    args: Dict[str, BlueprintArg] = Field(default_factory=dict)
    compose: List[str] = Field(default_factory=list)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = "builtin"
    score: int = 50
    use_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_used_at: Optional[str] = None
    fingerprint: Optional[str] = None
    retired: bool = False
    created_at: Optional[str] = None


class BlueprintSummary(BaseModel):
    """Summary view returned by list/search."""
    id: str
    name: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    args: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    source: Optional[str] = None
    score: Optional[int] = None
    use_count: Optional[int] = None

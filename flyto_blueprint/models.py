# Copyright 2024 Flyto2
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
    connections: Dict[str, str] = Field(default_factory=dict)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = "builtin"
    trust_tier: str = "community"
    score: int = 50
    compatibility: Dict[str, Any] = Field(default_factory=dict)
    verification: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    evidence_samples: List[Dict[str, Any]] = Field(default_factory=list)
    use_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    community_success_count: int = 0
    community_fail_count: int = 0
    community_success_rate: Optional[float] = None
    last_used_at: Optional[str] = None
    last_verified_at: Optional[str] = None
    last_community_observed_at: Optional[str] = None
    fingerprint: Optional[str] = None
    context_fingerprint: Optional[str] = None
    bundle_digest: Optional[str] = None
    retired: bool = False
    created_at: Optional[str] = None
    imported_at: Optional[str] = None


class BlueprintSummary(BaseModel):
    """Summary view returned by list/search."""
    id: str
    name: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    args: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    source: Optional[str] = None
    trust_tier: Optional[str] = None
    score: Optional[int] = None
    effective_score: Optional[float] = None
    use_count: Optional[int] = None
    community_observations: Optional[int] = None
    community_success_rate: Optional[float] = None
    compatibility: Dict[str, Any] = Field(default_factory=dict)
    evidence_card: Dict[str, Any] = Field(default_factory=dict)

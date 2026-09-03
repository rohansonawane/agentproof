from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentproof.core.faults import MutationSpec
from agentproof.core.trace import TraceEvent

RUN_ARTIFACT_SCHEMA_VERSION = 1


class RunArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = RUN_ARTIFACT_SCHEMA_VERSION
    run_id: str
    scenario: str
    seed: int
    mutation: MutationSpec | None
    initial_world_snapshot: dict[str, Any]
    trace: list[TraceEvent]
    violated_invariants: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

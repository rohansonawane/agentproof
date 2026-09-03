from __future__ import annotations

from agentproof.mutations.base import MUTATION_TYPES, Mutation, mutation_from_spec
from agentproof.mutations.duplication import DuplicateEvent, DuplicateUserRequest
from agentproof.mutations.ordering import ReorderToolResults
from agentproof.mutations.state import StaleState, StateChangedAfterRead
from agentproof.mutations.timing import DelayedEvent
from agentproof.mutations.tool_faults import (
    DuplicateToolResult,
    MalformedResponse,
    MissingField,
    PermissionDenied,
    RateLimited,
    TimeoutAfterCommit,
    ToolError,
    ToolLatency,
    ToolTimeout,
)


def standard_reliability_pack() -> list[Mutation]:
    """Return stable single-fault mutations used by the default deterministic pack."""

    return [
        ToolTimeout(),
        TimeoutAfterCommit(severity="high"),
        ToolError(),
        ToolLatency(params={"seconds": 1.0}),
        RateLimited(),
        MalformedResponse(),
        MissingField(params={"field": "status"}),
        DuplicateUserRequest(severity="high"),
        StaleState(params={"value": {}}),
        StateChangedAfterRead(params={"path": ["agentproof", "state_changed"], "value": True}),
        PermissionDenied(),
        DelayedEvent(),
        DuplicateEvent(),
    ]


__all__ = [
    "MUTATION_TYPES",
    "DelayedEvent",
    "DuplicateEvent",
    "DuplicateToolResult",
    "DuplicateUserRequest",
    "MalformedResponse",
    "MissingField",
    "Mutation",
    "PermissionDenied",
    "RateLimited",
    "ReorderToolResults",
    "StaleState",
    "StateChangedAfterRead",
    "TimeoutAfterCommit",
    "ToolError",
    "ToolLatency",
    "ToolTimeout",
    "mutation_from_spec",
    "standard_reliability_pack",
]

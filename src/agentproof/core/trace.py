from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentproof.core.redaction import redact

TraceKind = Literal[
    "user_input",
    "tool_call",
    "tool_result",
    "tool_error",
    "effect",
    "fault",
    "state_change",
    "event_scheduled",
    "event_delivered",
    "agent_output",
    "invariant_pass",
    "invariant_fail",
]


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int
    timestamp: float
    kind: TraceKind
    name: str
    data: dict[str, Any] = Field(default_factory=dict)


class TraceRecorder:
    def __init__(self, *, clock: Any) -> None:
        self._clock = clock
        self._events: list[TraceEvent] = []

    def record(self, kind: TraceKind, name: str, data: dict[str, Any] | None = None) -> TraceEvent:
        event = TraceEvent(
            seq=len(self._events) + 1,
            timestamp=float(self._clock.now()),
            kind=kind,
            name=name,
            data=redact(data or {}),
        )
        self._events.append(event)
        return event

    def all(self) -> list[TraceEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()

    def snapshot(self) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in self._events]

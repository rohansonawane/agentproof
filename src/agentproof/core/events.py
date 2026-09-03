from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScheduledEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    deliver_at: float
    delivered: bool = False


class EventQueue:
    def __init__(self, world: Any) -> None:
        self._world = world
        self._events: list[ScheduledEvent] = []

    def schedule(self, *, name: str, payload: dict[str, Any], delay: float = 0.0) -> ScheduledEvent:
        event = ScheduledEvent(
            id=self._world.next_id("event"),
            name=name,
            payload=copy.deepcopy(payload),
            deliver_at=float(self._world.clock.now()) + float(delay),
        )
        self._events.append(event)
        self._world.trace.record(
            "event_scheduled",
            name,
            {"event_id": event.id, "payload": payload, "deliver_at": event.deliver_at},
        )
        return event

    def deliver_due(self) -> list[ScheduledEvent]:
        delivered: list[ScheduledEvent] = []
        for event in self._events:
            if event.delivered or event.deliver_at > self._world.clock.now():
                continue
            if self._world.faults.before_event_delivery(event):
                continue
            event.delivered = True
            for index in range(self._world.faults.duplicate_event_count(event)):
                payload = copy.deepcopy(event.payload)
                delivered_event = event.model_copy(deep=True)
                delivered_event.id = event.id if index == 0 else f"{event.id}_dup_{index}"
                delivered.append(delivered_event)
                self._world.trace.record(
                    "event_delivered",
                    event.name,
                    {"event_id": delivered_event.id, "payload": payload},
                )
        return delivered

    def pending(self) -> list[ScheduledEvent]:
        return [event.model_copy(deep=True) for event in self._events if not event.delivered]

    def snapshot(self) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in self._events]

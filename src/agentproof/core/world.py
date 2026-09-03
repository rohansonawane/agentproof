from __future__ import annotations

import copy
import random
from collections.abc import Iterator, MutableMapping
from typing import Any

from agentproof.core.clock import VirtualClock
from agentproof.core.effects import EffectLedger
from agentproof.core.events import EventQueue
from agentproof.core.faults import FaultController
from agentproof.core.redaction import redact
from agentproof.core.trace import TraceRecorder


class StateStore(MutableMapping[str, Any]):
    def __init__(self, world: World, data: dict[str, Any] | None = None) -> None:
        object.__setattr__(self, "_world", world)
        object.__setattr__(self, "_data", copy.deepcopy(data or {}))
        object.__setattr__(self, "_trace_enabled", True)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value
        if self._trace_enabled:
            self._world.trace.record(
                "state_change", key, {"path": [key], "value": copy.deepcopy(value)}
            )

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        if self._trace_enabled:
            self._world.trace.record("state_change", key, {"path": [key], "deleted": True})

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getattr__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            self[key] = value

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def replace(self, data: dict[str, Any]) -> None:
        self._trace_enabled = False
        try:
            self._data.clear()
            self._data.update(copy.deepcopy(data))
        finally:
            self._trace_enabled = True


class World:
    """Stateful simulated environment exposed to an agent through virtual tools."""

    def __init__(self, *, seed: int = 0, metadata: dict[str, Any] | None = None) -> None:
        self.seed = seed
        self.random = random.Random(seed)
        self.clock = VirtualClock()
        self.trace = TraceRecorder(clock=self.clock)
        self.state = StateStore(self)
        self.effects = EffectLedger()
        self.faults = FaultController(self)
        self.events = EventQueue(self)
        self.metadata: dict[str, Any] = dict(metadata or {})
        self.user_inputs: list[str] = []
        self._id_counters: dict[str, int] = {}

        from agentproof.tools.registry import ToolRegistry

        self.tools = ToolRegistry(self)

    def input(self, text: str) -> None:
        self.user_inputs.append(text)
        self.trace.record("user_input", "user", {"text": text})

    def next_id(self, prefix: str) -> str:
        self._id_counters[prefix] = self._id_counters.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counters[prefix]:03d}"

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "clock": self.clock.now(),
            "state": self.state.snapshot(),
            "inputs": copy.deepcopy(self.user_inputs),
            "effects": self.effects.snapshot(),
            "metadata": redact(copy.deepcopy(self.metadata)),
        }

    def clone_from_initial(self) -> World:
        cloned = World(seed=self.seed, metadata=copy.deepcopy(self.metadata))
        cloned.state.replace(self.state.snapshot())
        cloned.user_inputs = copy.deepcopy(self.user_inputs)
        return cloned

    def set_path(self, path: list[Any], value: Any) -> None:
        if not path:
            raise ValueError("path must not be empty")
        cursor: Any = self.state._data
        for key in path[:-1]:
            cursor = cursor.setdefault(key, {}) if isinstance(cursor, dict) else cursor[key]
        final_key = path[-1]
        if isinstance(cursor, dict):
            cursor[final_key] = value
        else:
            cursor[final_key] = value
        self.trace.record(
            "state_change",
            ".".join(str(item) for item in path),
            {"path": path, "value": copy.deepcopy(value)},
        )

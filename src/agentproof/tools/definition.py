from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from agentproof.core.effects import EffectDraft

ToolEffect = Literal["read", "write", "delete", "external", "financial", "privileged"]
ToolHandler = Callable[..., Awaitable[Any] | Any]


@dataclass(frozen=True)
class ToolOutcome:
    value: Any
    effects: list[EffectDraft | dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    effect: ToolEffect | None = None
    idempotent: bool | None = None

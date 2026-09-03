from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class AgentRunResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    final_output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_result: Any | None = None


class AgentAdapter(Protocol):
    name: str

    async def run(self, *, world: Any, user_input: str) -> AgentRunResult: ...

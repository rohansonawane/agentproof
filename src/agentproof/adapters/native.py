from __future__ import annotations

import inspect
from typing import Any

from agentproof.adapters.base import AgentRunResult
from agentproof.tools.invocation import ToolClient


class NativeAdapter:
    name = "native"

    def __init__(self, agent: Any | None = None) -> None:
        self.agent = agent

    async def run(self, *, world: Any, user_input: str) -> AgentRunResult:
        if self.agent is None:
            raise ValueError("NativeAdapter requires an agent callable")
        tools = ToolClient(world)
        result = self.agent(user_input, tools)
        if inspect.isawaitable(result):
            result = await result
        return AgentRunResult(final_output=None if result is None else str(result))

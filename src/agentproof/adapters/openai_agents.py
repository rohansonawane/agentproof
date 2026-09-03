from __future__ import annotations

import json
from typing import Any

from agentproof.adapters.base import AgentRunResult


class OpenAIAgentsAdapter:
    """Adapter for the real OpenAI Agents SDK boundary."""

    name = "openai-agents"

    def __init__(self, agent: Any | None = None) -> None:
        self.agent = agent

    def build_function_tools(self, world: Any) -> list[Any]:
        try:
            from agents import FunctionTool
        except ImportError as exc:
            raise RuntimeError("Install agentproof-sim[openai] to use OpenAIAgentsAdapter") from exc

        wrapped = []
        for definition in world.tools.all():

            async def on_invoke_tool(
                ctx: Any, input: str, *, tool_name: str = definition.name
            ) -> Any:
                del ctx
                payload = json.loads(input or "{}")
                return await world.tools.invoke(tool_name, payload)

            wrapped.append(
                FunctionTool(
                    name=definition.name,
                    description=definition.description,
                    params_json_schema=definition.input_schema,
                    on_invoke_tool=on_invoke_tool,
                    strict_json_schema=False,
                )
            )
        return wrapped

    async def run(self, *, world: Any, user_input: str) -> AgentRunResult:
        if self.agent is None:
            raise ValueError("OpenAIAgentsAdapter requires an Agents SDK Agent for run()")
        try:
            from agents import Runner
        except ImportError as exc:
            raise RuntimeError("Install agentproof-sim[openai] to use OpenAIAgentsAdapter") from exc

        original_tools = list(getattr(self.agent, "tools", []))
        self.agent.tools = self.build_function_tools(world)
        try:
            result = await Runner.run(self.agent, user_input)
        finally:
            self.agent.tools = original_tools
        return AgentRunResult(
            final_output=str(getattr(result, "final_output", "")),
            metadata={"framework": "openai-agents"},
            raw_result=result,
        )

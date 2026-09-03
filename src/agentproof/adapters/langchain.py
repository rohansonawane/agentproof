from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, create_model

from agentproof.adapters.base import AgentRunResult


class LangChainAdapter:
    """Adapter for LangChain v1 / LangGraph tools backed by AgentProof."""

    name = "langchain-langgraph"

    def __init__(self, agent: Any | None = None) -> None:
        self.agent = agent

    def build_tools(self, world: Any) -> list[Any]:
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise RuntimeError("Install agentproof[langchain] to use LangChainAdapter") from exc

        tools = []
        for definition in world.tools.all():
            args_schema = _pydantic_model_from_schema(definition.name, definition.input_schema)

            tools.append(
                StructuredTool.from_function(
                    coroutine=_make_coroutine(world, definition.name),
                    name=definition.name,
                    description=definition.description,
                    args_schema=args_schema,
                )
            )
        return tools

    def create_agent(self, *, model: Any, world: Any, system_prompt: str | None = None) -> Any:
        try:
            from langchain.agents import create_agent
        except ImportError as exc:
            raise RuntimeError("Install agentproof[langchain] to use LangChainAdapter") from exc
        return create_agent(model=model, tools=self.build_tools(world), system_prompt=system_prompt)

    async def run(self, *, world: Any, user_input: str) -> AgentRunResult:
        if self.agent is None:
            raise ValueError("LangChainAdapter requires an agent/graph for run()")
        result = await self.agent.ainvoke({"messages": [{"role": "user", "content": user_input}]})
        return AgentRunResult(
            final_output=json.dumps(_json_safe(result), sort_keys=True),
            metadata={"framework": "langchain-langgraph"},
            raw_result=result,
        )


def _pydantic_model_from_schema(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, field_schema in properties.items():
        field_type = _python_type(field_schema)
        default = ... if field_name in required else None
        fields[field_name] = (field_type, default)
    return create_model(f"AgentProof{name.title().replace('_', '')}Input", **fields)  # type: ignore[call-overload]


def _make_coroutine(world: Any, tool_name: str) -> Any:
    async def call(**kwargs: Any) -> Any:
        return await world.tools.invoke(tool_name, kwargs)

    return call


def _python_type(schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list
    if schema_type == "object":
        return dict
    return str


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value

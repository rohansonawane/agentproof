from __future__ import annotations

import inspect
from typing import Any

from agentproof.core.faults import AgentProofToolError, ToolValidationError
from agentproof.tools.definition import ToolDefinition, ToolOutcome


class ToolRegistry:
    def __init__(self, world: Any) -> None:
        self._world = world
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
        effect: str | None = None,
        idempotent: bool | None = None,
    ) -> ToolDefinition:
        definition = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
            effect=effect,  # type: ignore[arg-type]
            idempotent=idempotent,
        )
        self._tools[name] = definition
        return definition

    def get(self, name: str) -> ToolDefinition:
        return self._tools[name]

    def all(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    async def invoke(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        args = dict(arguments or {})
        definition = self._tools[name]
        self._validate(definition, args)
        invocation_id = self._world.next_id("invocation")
        self._world.trace.record(
            "tool_call",
            name,
            {"arguments": args, "invocation_id": invocation_id},
        )

        action = self._world.faults.before_tool_call(
            tool_name=name,
            args=args,
            invocation_id=invocation_id,
        )
        if action is not None and action.handled:
            if action.exception is not None:
                self._world.trace.record(
                    "tool_error",
                    name,
                    {
                        "error_type": type(action.exception).__name__,
                        "message": str(action.exception),
                        "invocation_id": invocation_id,
                    },
                )
                raise action.exception
            self._world.trace.record(
                "tool_result",
                name,
                {"result": action.return_value, "invocation_id": invocation_id},
            )
            return action.return_value

        try:
            raw = await self._call_handler(definition, args)
        except AgentProofToolError:
            raise
        except Exception as exc:
            self._world.trace.record(
                "tool_error",
                name,
                {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "invocation_id": invocation_id,
                },
            )
            raise

        outcome = raw if isinstance(raw, ToolOutcome) else ToolOutcome(value=raw)
        for draft in outcome.effects:
            effect = self._world.effects.commit(
                draft,
                tool_name=name,
                invocation_id=invocation_id,
                committed_at=self._world.clock.now(),
            )
            self._world.trace.record(
                "effect",
                effect.type,
                {"effect": effect.model_dump(mode="json"), "invocation_id": invocation_id},
            )

        try:
            self._world.faults.after_commit_before_response(
                tool_name=name,
                invocation_id=invocation_id,
            )
        except AgentProofToolError as exc:
            self._world.trace.record(
                "tool_error",
                name,
                {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "invocation_id": invocation_id,
                },
            )
            raise

        response = self._world.faults.after_tool_response(
            tool_name=name,
            invocation_id=invocation_id,
            response=outcome.value,
        )
        self._world.trace.record(
            "tool_result",
            name,
            {"result": response, "invocation_id": invocation_id},
        )
        return response

    async def _call_handler(self, definition: ToolDefinition, args: dict[str, Any]) -> Any:
        signature = inspect.signature(definition.handler)
        kwargs = dict(args)
        if "world" in signature.parameters:
            kwargs["world"] = self._world
        result = definition.handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    @staticmethod
    def _validate(definition: ToolDefinition, args: dict[str, Any]) -> None:
        schema = definition.input_schema or {}
        required = schema.get("required", [])
        for field in required:
            if field not in args:
                raise ToolValidationError(definition.name, f"missing required field: {field}")

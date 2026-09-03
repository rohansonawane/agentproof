from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]


class AgentProofError(Exception):
    """Base exception for AgentProof-controlled errors."""


class AgentProofToolError(AgentProofError):
    code = "tool_error"

    def __init__(self, tool_name: str, message: str | None = None) -> None:
        self.tool_name = tool_name
        super().__init__(message or f"{self.code}: {tool_name}")


class ToolTimeoutError(AgentProofToolError, TimeoutError):
    code = "timeout"


class ToolRateLimitError(AgentProofToolError):
    code = "rate_limited"


class ToolPermissionDeniedError(AgentProofToolError):
    code = "permission_denied"


class ToolInjectedError(AgentProofToolError):
    code = "tool_error"


class ToolValidationError(AgentProofToolError):
    code = "validation_error"


class UnsupportedMutationError(AgentProofError):
    pass


class MutationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    target: str | None = None
    occurrence: int | None = 1
    params: dict[str, Any] = Field(default_factory=dict)
    severity: Severity = "medium"


@dataclass(frozen=True)
class PreCallAction:
    return_value: Any = None
    exception: AgentProofToolError | None = None
    handled: bool = False


class FaultController:
    def __init__(self, world: Any) -> None:
        self._world = world
        self._mutations: list[MutationSpec] = []
        self._counts: dict[tuple[str, str, str | None], int] = {}

    @property
    def mutations(self) -> list[MutationSpec]:
        return list(self._mutations)

    def install(self, spec: MutationSpec) -> None:
        if spec.type == "reorder_tool_results":
            raise UnsupportedMutationError(
                "reorder_tool_results requires a controlled parallel tool-result scheduler and "
                "is not stable in this MVP"
            )
        self._mutations.append(spec)

    def prepare_user_inputs(self, inputs: list[str]) -> list[str]:
        spec = self._match("before_agent_input", None, "duplicate_user_request")
        if spec is None:
            return list(inputs)
        if not inputs:
            return []
        index = int(spec.params.get("index", 0))
        index = min(max(index, 0), len(inputs) - 1)
        duplicated = list(inputs)
        duplicated.insert(index + 1, inputs[index])
        self._world.trace.record(
            "fault",
            "duplicate_user_request",
            {"mutation": spec.model_dump(mode="json"), "input": inputs[index]},
        )
        self._world.trace.record("user_input", "user", {"text": inputs[index], "duplicate": True})
        return duplicated

    def before_tool_call(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        invocation_id: str,
    ) -> PreCallAction | None:
        del args
        latency = self._match("before_tool_call", tool_name, "tool_latency")
        if latency is not None:
            seconds = float(latency.params.get("seconds", 1.0))
            self._world.clock.advance(seconds)
            self._world.trace.record(
                "fault",
                "tool_latency",
                {
                    "mutation": latency.model_dump(mode="json"),
                    "invocation_id": invocation_id,
                    "advanced_seconds": seconds,
                },
            )
            return None

        timeout = self._match("before_tool_call", tool_name, "tool_timeout")
        if timeout is not None:
            self._world.trace.record(
                "fault",
                "tool_timeout",
                {"mutation": timeout.model_dump(mode="json"), "invocation_id": invocation_id},
            )
            return PreCallAction(
                exception=ToolTimeoutError(tool_name, "tool timed out before commit"),
                handled=True,
            )

        injected = self._match("before_tool_call", tool_name, "tool_error")
        if injected is not None:
            self._world.trace.record(
                "fault",
                "tool_error",
                {"mutation": injected.model_dump(mode="json"), "invocation_id": invocation_id},
            )
            message = str(injected.params.get("message", "injected tool error"))
            return PreCallAction(exception=ToolInjectedError(tool_name, message), handled=True)

        rate_limited = self._match("before_tool_call", tool_name, "rate_limited")
        if rate_limited is not None:
            self._world.trace.record(
                "fault",
                "rate_limited",
                {"mutation": rate_limited.model_dump(mode="json"), "invocation_id": invocation_id},
            )
            return PreCallAction(
                exception=ToolRateLimitError(tool_name, "tool call was rate limited"),
                handled=True,
            )

        denied = self._match("before_tool_call", tool_name, "permission_denied")
        if denied is not None:
            self._world.trace.record(
                "fault",
                "permission_denied",
                {"mutation": denied.model_dump(mode="json"), "invocation_id": invocation_id},
            )
            return PreCallAction(
                exception=ToolPermissionDeniedError(tool_name, "permission denied"),
                handled=True,
            )

        stale = self._match("before_tool_call", tool_name, "stale_state")
        if stale is not None:
            if "value" not in stale.params:
                raise UnsupportedMutationError("stale_state requires params['value']")
            self._world.trace.record(
                "fault",
                "stale_state",
                {"mutation": stale.model_dump(mode="json"), "invocation_id": invocation_id},
            )
            return PreCallAction(return_value=stale.params["value"], handled=True)

        return None

    def after_commit_before_response(self, *, tool_name: str, invocation_id: str) -> None:
        spec = self._match("after_commit_before_response", tool_name, "timeout_after_commit")
        if spec is None:
            return
        self._world.trace.record(
            "fault",
            "timeout_after_commit",
            {"mutation": spec.model_dump(mode="json"), "invocation_id": invocation_id},
        )
        raise ToolTimeoutError(tool_name, "tool timed out after commit")

    def after_tool_response(
        self,
        *,
        tool_name: str,
        invocation_id: str,
        response: Any,
    ) -> Any:
        malformed = self._match("after_tool_response", tool_name, "malformed_response")
        if malformed is not None:
            self._world.trace.record(
                "fault",
                "malformed_response",
                {"mutation": malformed.model_dump(mode="json"), "invocation_id": invocation_id},
            )
            return malformed.params.get("value", "<<agentproof:malformed-response>>")

        missing = self._match("after_tool_response", tool_name, "missing_field")
        if missing is not None:
            field = missing.params.get("field")
            if not isinstance(field, str):
                raise UnsupportedMutationError("missing_field requires params['field']")
            self._world.trace.record(
                "fault",
                "missing_field",
                {
                    "mutation": missing.model_dump(mode="json"),
                    "invocation_id": invocation_id,
                    "field": field,
                },
            )
            if isinstance(response, dict):
                cloned = dict(response)
                cloned.pop(field, None)
                return cloned
            return response

        duplicate = self._match("after_tool_response", tool_name, "duplicate_tool_result")
        if duplicate is not None:
            self._world.trace.record(
                "fault",
                "duplicate_tool_result",
                {"mutation": duplicate.model_dump(mode="json"), "invocation_id": invocation_id},
            )
            return {"agentproof_duplicate_tool_result": [response, response]}

        changed = self._match("after_tool_response", tool_name, "state_changed_after_read")
        if changed is not None:
            path = changed.params.get("path")
            if not isinstance(path, list) or not path:
                raise UnsupportedMutationError("state_changed_after_read requires params['path']")
            value = changed.params.get("value")
            self._world.set_path(path, value)
            self._world.trace.record(
                "fault",
                "state_changed_after_read",
                {
                    "mutation": changed.model_dump(mode="json"),
                    "invocation_id": invocation_id,
                    "path": path,
                    "value": value,
                },
            )
            return response

        return response

    def before_event_delivery(self, event: Any) -> bool:
        delayed = self._match("before_event_delivery", event.name, "delayed_event")
        if delayed is None:
            return False
        delay = float(delayed.params.get("seconds", 1.0))
        event.deliver_at += delay
        self._world.trace.record(
            "fault",
            "delayed_event",
            {"mutation": delayed.model_dump(mode="json"), "event_id": event.id, "seconds": delay},
        )
        return True

    def duplicate_event_count(self, event: Any) -> int:
        duplicate = self._match("on_event_delivery", event.name, "duplicate_event")
        if duplicate is None:
            return 1
        count = int(duplicate.params.get("count", 2))
        self._world.trace.record(
            "fault",
            "duplicate_event",
            {"mutation": duplicate.model_dump(mode="json"), "event_id": event.id, "count": count},
        )
        return max(count, 1)

    def _match(self, stage: str, target: str | None, mutation_type: str) -> MutationSpec | None:
        for spec in self._mutations:
            if spec.type != mutation_type:
                continue
            if spec.target is not None and spec.target != target:
                continue
            key = (stage, mutation_type, spec.target)
            self._counts[key] = self._counts.get(key, 0) + 1
            if spec.occurrence is None or self._counts[key] == spec.occurrence:
                return spec
        return None

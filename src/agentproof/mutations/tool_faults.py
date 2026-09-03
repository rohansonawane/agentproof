from __future__ import annotations

from agentproof.mutations.base import Mutation, register_mutation


@register_mutation
class ToolTimeout(Mutation):
    mutation_type = "tool_timeout"
    description = "Raise a timeout before the virtual tool handler commits."


@register_mutation
class TimeoutAfterCommit(Mutation):
    mutation_type = "timeout_after_commit"
    description = "Commit the virtual tool outcome, then surface a timeout to the agent."


@register_mutation
class ToolError(Mutation):
    mutation_type = "tool_error"
    description = "Raise a configured tool error before the handler runs."


@register_mutation
class ToolLatency(Mutation):
    mutation_type = "tool_latency"
    description = "Advance the virtual clock without sleeping wall-clock time."


@register_mutation
class RateLimited(Mutation):
    mutation_type = "rate_limited"
    description = "Raise a recognizable rate-limit error before the handler runs."


@register_mutation
class MalformedResponse(Mutation):
    mutation_type = "malformed_response"
    description = "Replace a successful tool response with malformed deterministic data."


@register_mutation
class MissingField(Mutation):
    mutation_type = "missing_field"
    description = "Remove one configured field from a dictionary tool response."


@register_mutation
class DuplicateToolResult(Mutation):
    mutation_type = "duplicate_tool_result"
    description = "Return a deterministic envelope containing the same tool result twice."
    stable = False


@register_mutation
class PermissionDenied(Mutation):
    mutation_type = "permission_denied"
    description = "Raise a permission-denied error before the handler runs."

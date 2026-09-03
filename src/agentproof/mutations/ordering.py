from __future__ import annotations

from agentproof.mutations.base import Mutation, register_mutation


@register_mutation
class ReorderToolResults(Mutation):
    mutation_type = "reorder_tool_results"
    description = "Experimental placeholder for controlled parallel result reordering."
    stable = False

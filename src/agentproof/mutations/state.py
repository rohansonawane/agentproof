from __future__ import annotations

from agentproof.mutations.base import Mutation, register_mutation


@register_mutation
class StaleState(Mutation):
    mutation_type = "stale_state"
    description = "Return configured stale data for a read tool without changing canonical state."


@register_mutation
class StateChangedAfterRead(Mutation):
    mutation_type = "state_changed_after_read"
    description = "Mutate configured world state after a read response and before later actions."

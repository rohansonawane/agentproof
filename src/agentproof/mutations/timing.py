from __future__ import annotations

from agentproof.mutations.base import Mutation, register_mutation


@register_mutation
class DelayedEvent(Mutation):
    mutation_type = "delayed_event"
    description = "Push event delivery later on the virtual clock."

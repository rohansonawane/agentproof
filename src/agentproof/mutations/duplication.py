from __future__ import annotations

from agentproof.mutations.base import Mutation, register_mutation


@register_mutation
class DuplicateUserRequest(Mutation):
    mutation_type = "duplicate_user_request"
    description = "Deliver the same user input to the adapter twice in one run."


@register_mutation
class DuplicateEvent(Mutation):
    mutation_type = "duplicate_event"
    description = "Deliver a scheduled event more than once."

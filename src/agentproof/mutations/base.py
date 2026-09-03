from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from agentproof.core.faults import MutationSpec, Severity


@dataclass(frozen=True)
class Mutation:
    target: str | None = None
    occurrence: int | None = 1
    params: Mapping[str, Any] = field(default_factory=dict)
    severity: Severity = "medium"

    mutation_type: ClassVar[str] = "mutation"
    description: ClassVar[str] = "Generic mutation."
    stable: ClassVar[bool] = True

    @property
    def spec(self) -> MutationSpec:
        return MutationSpec(
            type=self.mutation_type,
            target=self.target,
            occurrence=self.occurrence,
            params=dict(self.params),
            severity=self.severity,
        )

    def install(self, world: Any) -> None:
        world.faults.install(self.spec)


def mutation_from_spec(spec: MutationSpec) -> Mutation:
    cls = MUTATION_TYPES.get(spec.type)
    if cls is None:
        return Mutation(
            target=spec.target,
            occurrence=spec.occurrence,
            params=spec.params,
            severity=spec.severity,
        )
    return cls(
        target=spec.target,
        occurrence=spec.occurrence,
        params=spec.params,
        severity=spec.severity,
    )


MUTATION_TYPES: dict[str, type[Mutation]] = {}


def register_mutation(cls: type[Mutation]) -> type[Mutation]:
    MUTATION_TYPES[cls.mutation_type] = cls
    return cls

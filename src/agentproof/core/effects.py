from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EffectDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    operation: str | None = None
    resource: str | None = None
    idempotency_key: str | None = None


class Effect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    tool_name: str
    operation: str | None = None
    resource: str | None = None
    data: dict[str, Any]
    committed_at: float
    idempotency_key: str | None = None
    invocation_id: str


class EffectLedger:
    """Records simulated side effects explicitly committed by virtual tool handlers."""

    def __init__(self) -> None:
        self._effects: list[Effect] = []

    def commit(
        self,
        draft: EffectDraft | dict[str, Any],
        *,
        tool_name: str,
        invocation_id: str,
        committed_at: float,
    ) -> Effect:
        draft_model = draft if isinstance(draft, EffectDraft) else EffectDraft.model_validate(draft)
        effect = Effect(
            id=f"eff_{len(self._effects) + 1:03d}",
            type=draft_model.type,
            tool_name=tool_name,
            operation=draft_model.operation,
            resource=draft_model.resource,
            data=draft_model.data,
            committed_at=committed_at,
            idempotency_key=draft_model.idempotency_key,
            invocation_id=invocation_id,
        )
        self._effects.append(effect)
        return effect

    def append(self, effect: Effect) -> None:
        self._effects.append(effect)

    def all(self) -> list[Effect]:
        return list(self._effects)

    def filter(
        self,
        *,
        type: str | None = None,
        where: dict[str, Any] | None = None,
        tool_name: str | None = None,
    ) -> list[Effect]:
        effects = self._effects
        if type is not None:
            effects = [effect for effect in effects if effect.type == type]
        if tool_name is not None:
            effects = [effect for effect in effects if effect.tool_name == tool_name]
        if where:
            effects = [
                effect
                for effect in effects
                if all(effect.data.get(key) == value for key, value in where.items())
            ]
        return list(effects)

    def sum(
        self,
        *,
        type: str,
        field: str,
        where: dict[str, Any] | None = None,
    ) -> float:
        total = 0.0
        for effect in self.filter(type=type, where=where):
            value = effect.data.get(field, 0)
            if isinstance(value, int | float):
                total += float(value)
        return total

    def duplicate_keys(self, *, type: str, key_fields: list[str]) -> dict[tuple[Any, ...], int]:
        counts: dict[tuple[Any, ...], int] = {}
        for effect in self.filter(type=type):
            key = tuple(effect.data.get(field) for field in key_fields)
            counts[key] = counts.get(key, 0) + 1
        return {key: count for key, count in counts.items() if count > 1}

    def snapshot(self) -> list[dict[str, Any]]:
        return [effect.model_dump(mode="json") for effect in self._effects]

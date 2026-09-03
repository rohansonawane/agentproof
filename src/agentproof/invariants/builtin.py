from __future__ import annotations

import fnmatch
from typing import Any

from agentproof.core.invariant import Invariant, invariant


def at_most_once(tool_name: str, *, severity: str = "medium") -> Invariant:
    return max_tool_calls(tool_name, 1, severity=severity)


def max_tool_calls(tool_name: str, count: int, *, severity: str = "medium") -> Invariant:
    @invariant(name=f"max_tool_calls_{tool_name}_{count}", severity=severity)
    def check(world: Any) -> None:
        observed = len(
            [
                event
                for event in world.trace.all()
                if event.kind == "tool_call" and event.name == tool_name
            ]
        )
        assert observed <= count, f"{tool_name} called {observed} times, expected <= {count}"

    return check


def never_call(tool_name: str, *, severity: str = "high") -> Invariant:
    @invariant(name=f"never_call_{tool_name}", severity=severity)
    def check(world: Any) -> None:
        observed = len(
            [
                event
                for event in world.trace.all()
                if event.kind == "tool_call" and event.name == tool_name
            ]
        )
        assert observed == 0, f"{tool_name} was called {observed} times"

    return check


def requires_before(required_tool: str, action_tool: str, *, severity: str = "high") -> Invariant:
    @invariant(name=f"requires_{required_tool}_before_{action_tool}", severity=severity)
    def check(world: Any) -> None:
        required_seen = False
        for event in world.trace.all():
            if event.kind == "tool_call" and event.name == required_tool:
                required_seen = True
            if event.kind == "tool_call" and event.name == action_tool:
                assert required_seen, f"{action_tool} called before {required_tool}"

    return check


def max_effect_sum(
    effect_type: str,
    field: str,
    maximum: float,
    *,
    where: dict[str, Any] | None = None,
    severity: str = "high",
) -> Invariant:
    @invariant(name=f"max_effect_sum_{effect_type}_{field}", severity=severity)
    def check(world: Any) -> None:
        observed = world.effects.sum(type=effect_type, field=field, where=where)
        assert observed <= maximum, f"{field} sum {observed:.2f}, expected <= {maximum:.2f}"

    return check


def no_duplicate_effects(
    effect_type: str,
    *,
    key_fields: list[str],
    severity: str = "high",
) -> Invariant:
    @invariant(name=f"no_duplicate_effects_{effect_type}", severity=severity)
    def check(world: Any) -> None:
        duplicates = world.effects.duplicate_keys(type=effect_type, key_fields=key_fields)
        assert not duplicates, f"duplicate {effect_type} effects for keys {duplicates}"

    return check


def forbid_resource(resource_pattern: str, *, severity: str = "critical") -> Invariant:
    @invariant(name=f"forbid_resource_{resource_pattern}", severity=severity)
    def check(world: Any) -> None:
        forbidden = [
            effect.resource
            for effect in world.effects.all()
            if effect.resource and fnmatch.fnmatch(effect.resource, resource_pattern)
        ]
        assert not forbidden, f"forbidden resources affected: {forbidden}"

    return check

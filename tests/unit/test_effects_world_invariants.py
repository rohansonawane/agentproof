from __future__ import annotations

import pytest

from agentproof import World, invariant
from agentproof.core.effects import EffectDraft
from agentproof.core.invariant import evaluate_invariants
from agentproof.invariants import (
    at_most_once,
    forbid_resource,
    max_effect_sum,
    never_call,
    no_duplicate_effects,
    requires_before,
)
from agentproof.tools.definition import ToolOutcome


def test_state_snapshot_is_deep_isolated() -> None:
    world = World(seed=1)
    world.state["orders"] = {"123": {"total": 49.0}}
    snapshot = world.snapshot()
    snapshot["state"]["orders"]["123"]["total"] = 99.0

    assert world.state["orders"]["123"]["total"] == 49.0


def test_clone_from_initial_deep_copies_state_and_inputs() -> None:
    world = World(seed=1)
    world.state["items"] = [{"id": "a"}]
    world.input("hello")

    cloned = world.clone_from_initial()
    cloned.state["items"][0]["id"] = "b"
    cloned.user_inputs.append("second")

    assert world.state["items"][0]["id"] == "a"
    assert world.user_inputs == ["hello"]


@pytest.mark.asyncio
async def test_effect_ledger_records_actual_effects_not_tool_calls() -> None:
    world = World(seed=1)

    async def no_effect_write(world: World) -> ToolOutcome:
        world.state["changed"] = True
        return ToolOutcome(value="ok")

    world.tools.register(
        name="write_without_effect",
        description="Mutates state but reports no external side effect.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=no_effect_write,
        effect="write",
        idempotent=False,
    )

    await world.tools.invoke("write_without_effect", {})

    assert [event.kind for event in world.trace.all()].count("tool_call") == 1
    assert world.effects.all() == []


@pytest.mark.asyncio
async def test_effect_filter_sum_and_duplicates() -> None:
    world = World(seed=1)

    async def refund() -> ToolOutcome:
        return ToolOutcome(
            value="ok",
            effects=[
                EffectDraft(type="refund.created", data={"order_id": "123", "amount": 10.0}),
                EffectDraft(type="refund.created", data={"order_id": "123", "amount": 10.0}),
            ],
        )

    world.tools.register(
        name="refund",
        description="refund",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=refund,
        effect="financial",
    )
    await world.tools.invoke("refund", {})

    assert world.effects.sum(type="refund.created", where={"order_id": "123"}, field="amount") == 20
    assert world.effects.duplicate_keys(type="refund.created", key_fields=["order_id", "amount"])


@pytest.mark.asyncio
async def test_invariant_failure_and_programming_error_are_distinct() -> None:
    world = World(seed=1)

    @invariant
    def fails(world: World) -> None:
        del world
        raise AssertionError("bad world")

    @invariant
    def errors(world: World) -> None:
        del world
        raise RuntimeError("test setup bug")

    failures, errors_found = await evaluate_invariants([fails, errors], world)

    assert failures[0].exception_type == "AssertionError"
    assert errors_found[0].exception_type == "RuntimeError"


@pytest.mark.asyncio
async def test_builtin_invariants() -> None:
    world = World(seed=1)

    async def approve() -> str:
        return "ok"

    async def delete() -> ToolOutcome:
        return ToolOutcome(
            value="deleted",
            effects=[
                EffectDraft(type="file.deleted", resource="/prod/db", data={"path": "/prod/db"})
            ],
        )

    for name, handler in {"approve": approve, "delete": delete}.items():
        world.tools.register(
            name=name,
            description=name,
            input_schema={"type": "object", "properties": {}, "required": []},
            handler=handler,
            effect="write",
        )

    await world.tools.invoke("approve", {})
    await world.tools.invoke("delete", {})

    checks = [
        at_most_once("delete"),
        max_effect_sum("file.deleted", "missing", 0),
        no_duplicate_effects("file.deleted", key_fields=["path"]),
        requires_before("approve", "delete"),
    ]
    failures, errors = await evaluate_invariants(checks, world)
    assert not failures
    assert not errors

    failures, _ = await evaluate_invariants(
        [never_call("delete"), forbid_resource("/prod/*")], world
    )
    assert {failure.name for failure in failures} == {
        "never_call_delete",
        "forbid_resource_/prod/*",
    }

from __future__ import annotations

import pytest

from agentproof import World
from agentproof.core.faults import (
    ToolInjectedError,
    ToolPermissionDeniedError,
    ToolRateLimitError,
    ToolTimeoutError,
    UnsupportedMutationError,
)
from agentproof.mutations import (
    DelayedEvent,
    DuplicateEvent,
    DuplicateToolResult,
    MalformedResponse,
    MissingField,
    PermissionDenied,
    RateLimited,
    ReorderToolResults,
    StaleState,
    StateChangedAfterRead,
    TimeoutAfterCommit,
    ToolError,
    ToolLatency,
    ToolTimeout,
)
from examples.refund_native.suite import _register_refund_tools


def make_world(*, idempotent: bool = False) -> World:
    world = World(seed=123)
    world.state["orders"] = {
        "123": {"id": "123", "total": 49.0, "status": "delivered", "refunded": 0.0}
    }
    world.state["refunds"] = []
    world.state["refund_idempotency"] = {}
    _register_refund_tools(world, idempotent=idempotent)
    return world


@pytest.mark.asyncio
async def test_timeout_before_commit_does_not_create_effect() -> None:
    world = make_world()
    ToolTimeout(target="refund_order").install(world)

    with pytest.raises(ToolTimeoutError):
        await world.tools.invoke("refund_order", {"order_id": "123", "amount": 49.0})

    assert world.effects.filter(type="refund.created") == []
    assert [event.kind for event in world.trace.all()].count("effect") == 0


@pytest.mark.asyncio
async def test_timeout_after_commit_commits_effect_then_times_out() -> None:
    world = make_world()
    TimeoutAfterCommit(target="refund_order").install(world)

    with pytest.raises(ToolTimeoutError):
        await world.tools.invoke("refund_order", {"order_id": "123", "amount": 49.0})

    effects = world.effects.filter(type="refund.created")
    assert len(effects) == 1
    kinds = [event.kind for event in world.trace.all()]
    assert kinds.index("effect") < kinds.index("fault") < kinds.index("tool_error")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "error_type"),
    [
        (ToolError(target="refund_order"), ToolInjectedError),
        (RateLimited(target="refund_order"), ToolRateLimitError),
        (PermissionDenied(target="refund_order"), ToolPermissionDeniedError),
    ],
)
async def test_pre_call_errors_do_not_commit_effects(
    mutation: object, error_type: type[Exception]
) -> None:
    world = make_world()
    mutation.install(world)  # type: ignore[attr-defined]

    with pytest.raises(error_type):
        await world.tools.invoke("refund_order", {"order_id": "123", "amount": 49.0})

    assert world.effects.filter(type="refund.created") == []


@pytest.mark.asyncio
async def test_tool_latency_advances_virtual_clock_without_sleeping() -> None:
    world = make_world()
    ToolLatency(target="get_order", params={"seconds": 9.5}).install(world)

    result = await world.tools.invoke("get_order", {"order_id": "123"})

    assert result["id"] == "123"
    assert world.clock.now() == 9.5


@pytest.mark.asyncio
async def test_malformed_response_is_observed_by_caller() -> None:
    world = make_world()
    MalformedResponse(target="get_order", params={"value": {"broken": True}}).install(world)

    assert await world.tools.invoke("get_order", {"order_id": "123"}) == {"broken": True}


@pytest.mark.asyncio
async def test_missing_field_removes_only_configured_field() -> None:
    world = make_world()
    MissingField(target="get_order", params={"field": "status"}).install(world)

    result = await world.tools.invoke("get_order", {"order_id": "123"})

    assert "status" not in result
    assert result["total"] == 49.0


@pytest.mark.asyncio
async def test_stale_state_returns_stale_value_without_mutating_canonical_state() -> None:
    world = make_world()
    stale = {"id": "123", "total": 1.0, "status": "processing"}
    StaleState(target="get_order", params={"value": stale}).install(world)

    result = await world.tools.invoke("get_order", {"order_id": "123"})

    assert result == stale
    assert world.state["orders"]["123"]["total"] == 49.0


@pytest.mark.asyncio
async def test_state_changed_after_read_mutates_world_after_return_value_is_built() -> None:
    world = make_world()
    StateChangedAfterRead(
        target="get_order",
        params={"path": ["orders", "123", "status"], "value": "cancelled"},
    ).install(world)

    result = await world.tools.invoke("get_order", {"order_id": "123"})

    assert result["status"] == "delivered"
    assert world.state["orders"]["123"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_duplicate_tool_result_has_explicit_experimental_envelope() -> None:
    world = make_world()
    DuplicateToolResult(target="get_order").install(world)

    result = await world.tools.invoke("get_order", {"order_id": "123"})

    assert set(result) == {"agentproof_duplicate_tool_result"}
    assert len(result["agentproof_duplicate_tool_result"]) == 2


def test_reorder_tool_results_is_not_claimed_stable() -> None:
    world = make_world()
    with pytest.raises(UnsupportedMutationError):
        ReorderToolResults(target="refund_order").install(world)


def test_delayed_event_waits_for_virtual_clock() -> None:
    world = make_world()
    DelayedEvent(target="shipment.updated", params={"seconds": 5}).install(world)
    world.events.schedule(name="shipment.updated", payload={"order_id": "123"}, delay=0)

    assert world.events.deliver_due() == []
    world.clock.advance(4.9)
    assert world.events.deliver_due() == []
    world.clock.advance(0.1)
    assert [event.name for event in world.events.deliver_due()] == ["shipment.updated"]


def test_duplicate_event_delivers_distinct_trace_events() -> None:
    world = make_world()
    DuplicateEvent(target="shipment.updated", params={"count": 2}).install(world)
    world.events.schedule(name="shipment.updated", payload={"order_id": "123"}, delay=0)

    delivered = world.events.deliver_due()

    assert len(delivered) == 2
    assert delivered[0].id != delivered[1].id
    assert [event.kind for event in world.trace.all()].count("event_delivered") == 2

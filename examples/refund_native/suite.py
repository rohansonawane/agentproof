from __future__ import annotations

import copy
from typing import Any

from agentproof import AgentTest, World, invariant
from agentproof.core.effects import EffectDraft
from agentproof.mutations import TimeoutAfterCommit
from agentproof.tools.definition import ToolOutcome

GET_ORDER_SCHEMA = {
    "type": "object",
    "properties": {"order_id": {"type": "string"}},
    "required": ["order_id"],
}
REFUND_SCHEMA = {
    "type": "object",
    "properties": {
        "order_id": {"type": "string"},
        "amount": {"type": "number"},
        "idempotency_key": {"type": "string"},
    },
    "required": ["order_id", "amount"],
}


async def naive_refund_agent(user_input: str, tools: Any) -> str:
    del user_input
    order = await tools.call("get_order", order_id="123")
    try:
        await tools.call("refund_order", order_id="123", amount=order["total"])
    except TimeoutError:
        await tools.call("refund_order", order_id="123", amount=order["total"])
    return "Done"


async def idempotent_refund_agent(user_input: str, tools: Any) -> str:
    del user_input
    order = await tools.call("get_order", order_id="123")
    key = "refund-order-123"
    try:
        await tools.call(
            "refund_order",
            order_id="123",
            amount=order["total"],
            idempotency_key=key,
        )
    except TimeoutError:
        await tools.call(
            "refund_order",
            order_id="123",
            amount=order["total"],
            idempotency_key=key,
        )
    return "Done"


def build_suite(*, idempotent: bool, mutations: list[Any] | None = None) -> AgentTest:
    agent = idempotent_refund_agent if idempotent else naive_refund_agent
    suite = AgentTest(
        agent=agent,
        adapter="native",
        mutations=mutations
        if mutations is not None
        else [TimeoutAfterCommit(target="refund_order", severity="high")],
        name="refund_native",
    )

    @suite.scenario(name="refund_delivered_order")
    async def refund_delivered_order(world: World) -> None:
        world.state["orders"] = {
            "123": {"id": "123", "total": 49.0, "status": "delivered", "refunded": 0.0}
        }
        world.state["refunds"] = []
        world.state["refund_idempotency"] = {}
        _register_refund_tools(world, idempotent=idempotent)
        world.input("Refund order 123")

    suite.add_invariant(no_double_refunds)
    return suite


def _register_refund_tools(world: World, *, idempotent: bool) -> None:
    async def get_order(world: World, order_id: str) -> dict[str, Any]:
        return copy.deepcopy(world.state["orders"][order_id])

    async def refund_order(
        world: World,
        order_id: str,
        amount: float,
        idempotency_key: str | None = None,
    ) -> ToolOutcome:
        if idempotent and idempotency_key:
            previous = world.state["refund_idempotency"].get(idempotency_key)
            if previous is not None:
                return ToolOutcome(value={"refund_id": previous, "idempotent_replay": True})
        refund_id = world.next_id("refund")
        world.state["refunds"].append(
            {
                "id": refund_id,
                "order_id": order_id,
                "amount": amount,
                "idempotency_key": idempotency_key,
            }
        )
        if idempotent and idempotency_key:
            world.state["refund_idempotency"][idempotency_key] = refund_id
        return ToolOutcome(
            value={"refund_id": refund_id},
            effects=[
                EffectDraft(
                    type="refund.created",
                    operation="create",
                    resource=f"order:{order_id}",
                    data={"refund_id": refund_id, "order_id": order_id, "amount": amount},
                    idempotency_key=idempotency_key,
                )
            ],
        )

    world.tools.register(
        name="get_order",
        description="Return a simulated order.",
        input_schema=GET_ORDER_SCHEMA,
        handler=get_order,
        effect="read",
        idempotent=True,
    )
    world.tools.register(
        name="refund_order",
        description="Create a simulated refund for an order.",
        input_schema=REFUND_SCHEMA,
        handler=refund_order,
        effect="financial",
        idempotent=idempotent,
    )


@invariant(severity="high")
def no_double_refunds(world: World) -> None:
    total = world.effects.sum(
        type="refund.created",
        where={"order_id": "123"},
        field="amount",
    )
    assert total <= 49.0, f"refunded ${total:.2f}, expected <= $49.00"


suite = build_suite(idempotent=False)

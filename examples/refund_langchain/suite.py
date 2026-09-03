from __future__ import annotations

from agentproof import World
from agentproof.adapters.langchain import LangChainAdapter
from examples.refund_native.suite import _register_refund_tools


def build_world(*, idempotent: bool = False) -> World:
    world = World(seed=42)
    world.state["orders"] = {
        "123": {"id": "123", "total": 49.0, "status": "delivered", "refunded": 0.0}
    }
    world.state["refunds"] = []
    world.state["refund_idempotency"] = {}
    _register_refund_tools(world, idempotent=idempotent)
    return world


def build_tools() -> list[object]:
    return LangChainAdapter().build_tools(build_world())

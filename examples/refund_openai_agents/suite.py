from __future__ import annotations

import asyncio
import os

from agentproof import World
from agentproof.adapters.openai_agents import OpenAIAgentsAdapter
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


async def run_live_if_enabled() -> None:
    if os.environ.get("AGENTPROOF_RUN_LIVE_TESTS") != "1" or not os.environ.get("OPENAI_API_KEY"):
        print("OpenAI live run skipped; set AGENTPROOF_RUN_LIVE_TESTS=1 and OPENAI_API_KEY.")
        return
    from agents import Agent

    world = build_world()
    adapter = OpenAIAgentsAdapter(
        Agent(
            name="Refund assistant",
            instructions="Refund order 123 using the available tools. Be concise.",
            tools=[],
            model=os.environ.get("AGENTPROOF_OPENAI_MODEL", "gpt-5.6"),
        )
    )
    result = await adapter.run(world=world, user_input="Refund order 123")
    print(result.final_output)
    print(world.effects.snapshot())


if __name__ == "__main__":
    asyncio.run(run_live_if_enabled())

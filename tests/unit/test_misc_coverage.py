from __future__ import annotations

import pytest

from agentproof import AgentTest, World, invariant
from agentproof.adapters.langchain import LangChainAdapter
from agentproof.adapters.native import NativeAdapter
from agentproof.adapters.openai_agents import OpenAIAgentsAdapter
from agentproof.core.effects import Effect
from agentproof.core.faults import ToolValidationError
from agentproof.core.trace import TraceEvent
from agentproof.invariants.temporal import requires_before
from agentproof.mutations import ToolTimeout, standard_reliability_pack
from agentproof.tools.definition import ToolOutcome


def test_public_api_and_small_helpers() -> None:
    world = World(seed=7)
    world.state.orders = {"123": {"total": 49}}
    assert world.state.orders["123"]["total"] == 49
    del world.state["orders"]
    with pytest.raises(AttributeError):
        _ = world.state.orders

    event = world.trace.record("agent_output", "native", {"ok": True})
    assert isinstance(event, TraceEvent)
    assert event.seq == 3
    assert world.trace.snapshot()[-1]["seq"] == 3
    world.trace.clear()
    assert world.trace.all() == []

    world.clock.set(12)
    assert world.clock.now() == 12
    with pytest.raises(ValueError):
        world.clock.advance(-1)

    effect = Effect(
        id="eff_x",
        type="manual",
        tool_name="tool",
        data={},
        committed_at=12,
        invocation_id="inv_x",
    )
    world.effects.append(effect)
    assert world.effects.filter(tool_name="tool") == [effect]
    assert world.events.pending() == []
    assert world.events.snapshot() == []
    assert requires_before("a", "b").name == "requires_a_before_b"
    assert standard_reliability_pack()


async def test_tool_validation_and_registry_get() -> None:
    world = World(seed=1)

    async def read(required: str) -> str:
        return required

    world.tools.register(
        name="read",
        description="read",
        input_schema={
            "type": "object",
            "properties": {"required": {"type": "string"}},
            "required": ["required"],
        },
        handler=read,
        effect="read",
    )

    assert world.tools.get("read").name == "read"
    with pytest.raises(KeyError):
        world.tools.get("missing")
    with pytest.raises(ToolValidationError):
        await world.tools.invoke("read", {})


async def test_adapter_error_paths() -> None:
    with pytest.raises(ValueError):
        await NativeAdapter().run(world=World(), user_input="hi")
    with pytest.raises(ValueError):
        await OpenAIAgentsAdapter().run(world=World(), user_input="hi")
    with pytest.raises(ValueError):
        await LangChainAdapter().run(world=World(), user_input="hi")


def test_run_sync() -> None:
    async def agent(user_input: str, tools: object) -> str:
        del user_input, tools
        return "ok"

    suite = AgentTest(agent=agent, mutations=[ToolTimeout(target="unused")])

    @suite.scenario
    def scenario(world: World) -> None:
        world.input("hello")

    @invariant
    def ok(world: World) -> None:
        assert world.user_inputs == ["hello"]

    result = suite.run_sync(store_artifacts=False)
    assert result.passed_count == 2
    assert result.exit_code("critical") == 0


async def test_invariant_direct_check_methods() -> None:
    @invariant
    def fails(world: World) -> None:
        del world
        raise AssertionError("no")

    @invariant
    def errors(world: World) -> None:
        del world
        raise RuntimeError("boom")

    assert await fails.check(World()) is not None
    assert await errors.check_programming_error(World()) is not None


async def test_raw_tool_result_is_wrapped_as_outcome() -> None:
    world = World(seed=1)

    async def raw() -> str:
        return "raw"

    async def outcome() -> ToolOutcome:
        return ToolOutcome(value="outcome")

    world.tools.register(
        name="raw",
        description="raw",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=raw,
    )
    world.tools.register(
        name="outcome",
        description="outcome",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=outcome,
    )

    assert await world.tools.invoke("raw", {}) == "raw"
    assert await world.tools.invoke("outcome", {}) == "outcome"

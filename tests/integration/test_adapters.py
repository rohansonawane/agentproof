from __future__ import annotations

from typing import Annotated, TypedDict

import pytest

from agentproof.adapters.langchain import LangChainAdapter
from agentproof.adapters.openai_agents import OpenAIAgentsAdapter
from agentproof.core.faults import ToolTimeoutError
from agentproof.mutations import TimeoutAfterCommit
from examples.refund_langchain.suite import build_world as build_langchain_world
from examples.refund_native.suite import GET_ORDER_SCHEMA
from examples.refund_openai_agents.suite import build_world as build_openai_world


@pytest.mark.openai
async def test_openai_agents_function_tool_invocation_uses_real_sdk_boundary() -> None:
    agents = pytest.importorskip("agents")
    world = build_openai_world()
    adapter = OpenAIAgentsAdapter()

    tools = adapter.build_function_tools(world)
    get_order = next(tool for tool in tools if tool.name == "get_order")

    assert isinstance(get_order, agents.FunctionTool)
    assert get_order.params_json_schema == GET_ORDER_SCHEMA
    result = await get_order.on_invoke_tool(None, '{"order_id": "123"}')

    assert result["id"] == "123"
    assert any(
        event.kind == "tool_call" and event.name == "get_order" for event in world.trace.all()
    )


@pytest.mark.openai
async def test_openai_agents_function_tool_propagates_timeout_after_commit() -> None:
    pytest.importorskip("agents")
    world = build_openai_world()
    TimeoutAfterCommit(target="refund_order").install(world)
    refund = next(
        tool
        for tool in OpenAIAgentsAdapter().build_function_tools(world)
        if tool.name == "refund_order"
    )

    with pytest.raises(ToolTimeoutError):
        await refund.on_invoke_tool(None, '{"order_id": "123", "amount": 49.0}')

    assert len(world.effects.filter(type="refund.created")) == 1


@pytest.mark.langchain
async def test_langchain_structured_tool_invocation_uses_real_wrapper() -> None:
    pytest.importorskip("langchain")
    world = build_langchain_world()
    tools = LangChainAdapter().build_tools(world)
    get_order = next(tool for tool in tools if tool.name == "get_order")

    result = await get_order.ainvoke({"order_id": "123"})

    assert result["id"] == "123"
    assert any(
        event.kind == "tool_call" and event.name == "get_order" for event in world.trace.all()
    )


@pytest.mark.langchain
async def test_langgraph_compiled_tool_node_executes_agentproof_tool() -> None:
    pytest.importorskip("langchain")
    from langchain.agents import create_agent
    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode

    world = build_langchain_world()
    tools = LangChainAdapter().build_tools(world)
    assert callable(create_agent)

    state_type = TypedDict("LangGraphToolState", {"messages": Annotated[list, add_messages]})
    graph = StateGraph(state_type)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    app = graph.compile()

    output = await app.ainvoke(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_order",
                            "args": {"order_id": "123"},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }
    )

    assert isinstance(output["messages"][-1], ToolMessage)
    assert output["messages"][-1].name == "get_order"
    assert any(
        event.kind == "tool_call" and event.name == "get_order" for event in world.trace.all()
    )

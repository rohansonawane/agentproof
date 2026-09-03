# Adapters

Native: calls async or sync Python functions with `(user_input, tools)`.

OpenAI Agents SDK: builds real `agents.FunctionTool` objects whose `on_invoke_tool` callback calls `world.tools.invoke(...)`.

LangChain/LangGraph: builds real LangChain `StructuredTool` objects and is tested through a compiled LangGraph `StateGraph` containing `ToolNode`.

Live LLM tests are excluded from default test runs and require both `AGENTPROOF_RUN_LIVE_TESTS=1` and provider credentials.


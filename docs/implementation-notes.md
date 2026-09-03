# Implementation Notes

Verified documentation during implementation:

- OpenAI Agents SDK: `developers.openai.com/api/docs/guides/agents`, `developers.openai.com/api/docs/guides/agents/quickstart`, plus OpenAI Agents SDK API pages for `Agent`, `Runner`, `FunctionTool`, and tools.
- LangChain/LangGraph: `docs.langchain.com/oss/python/langchain/agents`, `docs.langchain.com/oss/python/langchain/tools`, and `docs.langchain.com/oss/python/migrate/langgraph-v1`.

Current adapter choices:

- Use `FunctionTool(..., on_invoke_tool=...)` for OpenAI Agents SDK local boundary tests.
- Use LangChain `StructuredTool` plus LangGraph `StateGraph`/`ToolNode` for local execution-boundary tests. Direct `ToolNode.ainvoke` requires LangGraph runtime configuration in the tested version, so the integration test compiles a graph before invoking it.


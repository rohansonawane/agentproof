# Architecture

AgentProof runs a real agent against an isolated simulated `World`. The world owns state, tools, effects, events, faults, a virtual clock, and an ordered trace.

Virtual tools separate the commit boundary from the observed response. A handler returns `ToolOutcome(value=..., effects=[...])`; the registry commits those effects before post-commit faults such as `timeout_after_commit` can convert the observed result into a timeout.

Core code does not import optional agent frameworks. The native, OpenAI Agents SDK, and LangChain/LangGraph adapters wrap AgentProof tools at their own framework boundaries.


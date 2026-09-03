# Changelog

## 0.1.0

- Initial technical-preview implementation.
- Deterministic `World` model with isolated state, tools, effects, faults, invariants, replay artifacts, traces, and virtual time.
- Stable fault mutations for tool timeouts, timeout-after-commit, tool errors, latency, rate limits, malformed responses, missing fields, duplicated user requests, stale state, permission denial, delayed events, and duplicated events.
- CLI support for CI gating, JSON reports, and JUnit reports.
- Pytest plugin marker registration.
- Native Python adapter.
- OpenAI Agents SDK adapter boundary using real SDK `FunctionTool` objects.
- LangChain/LangGraph adapter boundary using real `StructuredTool`, `StateGraph`, and `ToolNode` APIs.
- Runnable README quickstart for double-refund detection.
- Real external LangChain booking-app smoke test for duplicate booking detection.
- Release-hardening script for local validation, clean wheel install, README execution, optional extras, opt-in live OpenAI smoke tests, and hosted GitHub CI checks.
- GitHub repository hardening: issue templates, PR template, branch protection, secret scanning, push protection, Dependabot security updates, and GitHub Actions dependency monitoring.

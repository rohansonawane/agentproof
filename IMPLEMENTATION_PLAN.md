# Implementation Plan

## Phase 1: Foundation

- Add `src/` package, `pyproject.toml`, CI/release workflow skeletons, docs, license, and tests.

## Phase 2: Core Engine

- Implement `World`, `StateStore`, `ToolRegistry`, `EffectLedger`, `TraceRecorder`, virtual clock, event queue, and native adapter.

## Phase 3: Faults and Invariants

- Implement stable mutations, invariant decorator/evaluator, built-in invariants, and refund acceptance tests.

## Phase 4: Replay and Reports

- Persist deterministic repro artifacts and add console, JSON, and JUnit reports.

## Phase 5: Integrations

- Add OpenAI Agents SDK `FunctionTool` wrapper tests and LangChain/LangGraph `StructuredTool`/`ToolNode` tests.

## Phase 6: Release Validation

- Run deterministic checks, build wheel, install in a clean environment, execute README/example smoke tests, and update `RELEASE_VALIDATION.md` with only verified facts.


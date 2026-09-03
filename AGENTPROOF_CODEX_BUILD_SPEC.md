# AgentProof — Codex Build, Test, and Publish Specification

**Document status:** MVP implementation specification  
**Primary audience:** Codex / senior Python engineer / founding engineer  
**Target:** Public open-source MVP (`agentproof`)  
**Language:** Python 3.11+  
**Package manager:** `uv` preferred; must remain installable with `pip`  
**License:** Apache-2.0 unless project owner explicitly changes it  
**Initial integrations:** Native Python agents, OpenAI Agents SDK, LangChain/LangGraph  
**Primary deliverable:** A production-quality open-source Python package that can discover, explain, reproduce, and regression-test action-level failures in AI agents.

---

# 0. Codex Operating Instructions

You are building **AgentProof**, an open-source reliability testing framework for AI agents that take actions through tools.

Do not treat this as a prototype-generation task. Work as if the repository will be publicly released and reviewed by experienced Python, distributed-systems, and AI-infrastructure engineers.

## Non-negotiable operating rules

1. **Do not fake functionality.** If a mutation, adapter, replay mode, or CLI command is documented as supported, it must have an automated test proving it.
2. **Do not fake live-agent results.** Tests that claim to use OpenAI Agents SDK or LangChain/LangGraph must actually instantiate and execute those frameworks. Live LLM tests must be separately marked and require explicit API credentials.
3. **Never call real destructive external services in tests.** Refunds, email sends, file deletions, deployments, and similar effects must be virtualized.
4. **Prefer deterministic validation.** Critical pass/fail decisions must use state/invariant assertions, not an LLM judge.
5. **Keep the core framework independent of any single agent framework.** Framework-specific code belongs behind adapters.
6. **Implement the smallest complete architecture.** Do not build a SaaS dashboard, authentication, billing, hosted runners, or a web UI for this MVP.
7. **Every bug discovered by AgentProof must be reproducible.** Store a seed and mutation specification. For deterministic tests, `agentproof replay <artifact>` must reproduce the same invariant violation.
8. **Every run must use an isolated world.** No mutated world state may leak into another mutation run.
9. **No arbitrary `eval()` or untrusted code execution.** The test framework itself must not introduce obvious security hazards.
10. **Use type hints throughout.** Public APIs should have docstrings and stable semantics.
11. **Keep dependencies conservative.** Core AgentProof must not require OpenAI, LangChain, or LangGraph. Put those behind optional extras.
12. **Run tests after each implementation phase.** Do not postpone validation until the end.
13. **If current third-party APIs differ from this document, verify against the latest official documentation and adapt the implementation while preserving the intent.** Record deviations in `docs/implementation-notes.md`.
14. **Do not silently reduce scope.** If something cannot be implemented correctly, mark it clearly as deferred and remove it from public claims/README until it works.

## Development loop

For every phase:

1. inspect current repository state;
2. implement the smallest coherent slice;
3. add unit tests;
4. add integration tests where relevant;
5. run formatting, linting, type checking, and tests;
6. fix failures;
7. update documentation;
8. commit-ready state before continuing.

Do not publish to PyPI or push a GitHub release unless explicitly authorized by the repository owner. Build and validate the release workflow, but treat actual publication as a final manual/authorized step.

---

# 1. Product Definition

## 1.1 One-line definition

**AgentProof is a stateful simulation and fault-injection testing framework for AI agents that take real-world actions through tools.**

## 1.2 Core promise

> Test what your AI agent does to the world, not just what it says.

AgentProof creates an isolated simulated environment, exposes virtual tools to a real agent, injects realistic failures into those tools/environment, records resulting side effects, and checks deterministic invariants over the final world state.

## 1.3 Primary category

Agent reliability engineering / stateful agent testing / agent chaos testing.

It is intentionally **not** primarily:

- prompt evaluation;
- RAG evaluation;
- response grading;
- generic LLM observability;
- prompt management;
- synthetic conversation scoring;
- generic red-team-only tooling;
- an agent framework;
- an MCP gateway;
- an agent runtime.

## 1.4 Initial user

Python developers and engineering teams building agents that can perform state-changing actions, such as:

- refunds and payments;
- sending messages/emails;
- modifying CRM records;
- scheduling/canceling events;
- file changes;
- cloud/DevOps actions;
- support workflows;
- coding-agent repository changes;
- back-office automation.

---

# 2. MVP Success Definition

The MVP is successful only when all of the following are true:

- `pip install agentproof` installs successfully from a built wheel in a clean environment.
- A developer can define a world with virtual stateful tools.
- A developer can define deterministic invariants.
- AgentProof executes a baseline scenario.
- AgentProof automatically reruns the scenario with at least the required MVP mutations.
- The `timeout_after_commit` mutation can reveal a double-side-effect bug.
- AgentProof records the exact tool call, committed effect, injected fault, retry, second effect, and invariant failure.
- A failing deterministic run can be replayed from a persisted reproduction artifact.
- CLI exits nonzero for configured failing severity, so it can gate CI.
- Native Python adapter works.
- OpenAI Agents SDK integration works with an actual SDK agent.
- LangChain/LangGraph integration works with an actual framework agent.
- At least one live LLM end-to-end test can be run using an environment variable/API key, but live API tests are excluded from default CI.
- Unit/integration test suite passes without external API credentials.
- Package builds via standard Python packaging tooling.
- README contains a runnable five-minute example.
- GitHub Actions CI validates supported Python versions.
- A release workflow exists using PyPI Trusted Publishing/OIDC and is disabled from accidental publication until configured.

---

# 3. The Killer MVP Demo

The canonical demo is a refund agent.

## 3.1 Simulated domain

Initial world state:

```text
Order #123
Total: $49.00
Status: delivered
Refunded: $0
```

Virtual tools:

- `get_order(order_id)` — read-only
- `refund_order(order_id, amount, idempotency_key=None)` — side-effecting

User request:

```text
Refund order 123.
```

Baseline behavior:

1. agent calls `get_order("123")`;
2. agent calls `refund_order("123", 49)`;
3. one refund is recorded;
4. invariant passes.

Faulted behavior:

1. agent calls `get_order("123")`;
2. agent calls `refund_order("123", 49)`;
3. virtual refund service **commits** the refund;
4. AgentProof suppresses the success response and raises a timeout;
5. the naive agent retries;
6. the second refund commits;
7. final refund total becomes $98;
8. invariant fails.

Invariant:

```python
@invariant
def no_double_refunds(world):
    assert world.refunds.total_for("123") <= world.orders["123"].total
```

Expected terminal report:

```text
AgentProof

Scenario: refund_delivered_order
Baseline: PASS

Mutations
✓ tool_error:get_order
✓ latency:get_order
✓ rate_limited:refund_order
✓ duplicate_user_request
✗ timeout_after_commit:refund_order

INVARIANT VIOLATION
no_double_refunds

Expected refunded <= $49.00
Observed refunded = $98.00

Trace
1 USER       Refund order 123
2 TOOL_CALL  get_order(order_id="123")
3 TOOL_OK    {status:"delivered", total:49.0}
4 TOOL_CALL  refund_order(order_id="123", amount=49.0)
5 EFFECT     RefundCreated(order_id="123", amount=49.0)
6 FAULT      TimeoutAfterCommit(refund_order)
7 TOOL_CALL  refund_order(order_id="123", amount=49.0)
8 EFFECT     RefundCreated(order_id="123", amount=49.0)
9 TOOL_OK    refund_002
10 FAIL      no_double_refunds

Reproduce:
agentproof replay .agentproof/runs/<run-id>/repro.json
```

## 3.2 Fixed demo

Provide a second agent/tool implementation using an idempotency key. Run the same mutation suite and show that the refund remains $49.

This demonstrates both **bug discovery** and **regression protection**.

---

# 4. Core Design Principles

## 4.1 Stateful world, not text-only evaluation

A `World` contains:

- domain state;
- virtual tools;
- side effects;
- event queue;
- virtual clock;
- mutation/fault controller;
- execution trace;
- metadata.

## 4.2 Side-effect semantics are first-class

Every tool invocation may generate zero or more explicit side effects. AgentProof must separate:

- **operation committed** from
- **caller observed success**.

This separation is required for `timeout_after_commit`.

## 4.3 Invariants decide correctness

The primary evaluator is deterministic Python logic over world state/trace/effects.

Examples:

- total refund may not exceed order total;
- one user intent may not send duplicate email;
- deleting production is forbidden;
- a privileged action requires prior approval;
- external spend may not exceed a threshold;
- tool call count may not exceed a maximum.

## 4.4 Framework-neutral agent boundary

Core execution uses an adapter protocol. The core runner must not import framework packages.

## 4.5 Faults are explicit and serializable

Every mutation must be representable as data so the exact test can be stored and replayed.

---

# 5. Package and Repository Structure

Create the repository approximately as follows:

```text
agentproof/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── .gitignore
├── LICENSE
├── README.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── SECURITY.md
├── pyproject.toml
├── uv.lock
├── docs/
│   ├── architecture.md
│   ├── concepts.md
│   ├── mutations.md
│   ├── adapters.md
│   ├── implementation-notes.md
│   └── publishing.md
├── src/
│   └── agentproof/
│       ├── __init__.py
│       ├── py.typed
│       ├── api.py
│       ├── core/
│       │   ├── world.py
│       │   ├── runner.py
│       │   ├── scenario.py
│       │   ├── invariant.py
│       │   ├── effects.py
│       │   ├── events.py
│       │   ├── trace.py
│       │   ├── clock.py
│       │   ├── faults.py
│       │   └── result.py
│       ├── tools/
│       │   ├── registry.py
│       │   ├── definition.py
│       │   └── invocation.py
│       ├── mutations/
│       │   ├── base.py
│       │   ├── tool_faults.py
│       │   ├── timing.py
│       │   ├── duplication.py
│       │   ├── state.py
│       │   └── ordering.py
│       ├── invariants/
│       │   ├── builtin.py
│       │   └── temporal.py
│       ├── adapters/
│       │   ├── base.py
│       │   ├── native.py
│       │   ├── openai_agents.py
│       │   └── langchain.py
│       ├── replay/
│       │   ├── schema.py
│       │   ├── recorder.py
│       │   └── player.py
│       ├── reporting/
│       │   ├── console.py
│       │   ├── json_report.py
│       │   └── junit.py
│       ├── pytest_plugin.py
│       └── cli.py
├── examples/
│   ├── refund_native/
│   ├── refund_openai_agents/
│   ├── refund_langchain/
│   └── calendar_native/
└── tests/
    ├── unit/
    ├── integration/
    ├── e2e/
    └── fixtures/
```

Use `src/` layout.

---

# 6. Packaging Requirements

## 6.1 Package metadata

Use modern `pyproject.toml` packaging. Prefer Hatchling or another lightweight PEP 517 backend.

Suggested project name:

```toml
[project]
name = "agentproof"
```

If the PyPI name is unavailable, do **not** silently rename the project. Report the collision and wait for owner choice.

## 6.2 Supported Python

Target:

```text
Python >=3.11
```

CI matrix should test at least 3.11, 3.12, and 3.13 if dependencies support them.

## 6.3 Core dependencies

Keep minimal. Reasonable core dependencies include:

- `pydantic>=2`
- `typer` or `click` for CLI
- `rich` for readable terminal output
- `typing-extensions` only if needed

Do not put OpenAI/LangChain dependencies in core requirements.

## 6.4 Optional dependencies

Define extras, for example:

```toml
[project.optional-dependencies]
openai = ["openai-agents>=..."]
langchain = ["langchain>=...", "langgraph>=..."]
test = ["pytest>=...", "pytest-asyncio>=...", "pytest-cov>=..."]
dev = ["ruff>=...", "mypy>=...", "build>=...", "twine>=..."]
```

Use currently compatible minimum versions based on official package metadata during implementation.

## 6.5 CLI entrypoint

```toml
[project.scripts]
agentproof = "agentproof.cli:app"
```

## 6.6 Pytest plugin entrypoint

Pytest discovers external plugins through the `pytest11` entry-point group. Expose the plugin as:

```toml
[project.entry-points.pytest11]
agentproof = "agentproof.pytest_plugin"
```

Verify installation with:

```bash
pytest --trace-config
```

and assert AgentProof is loaded.

---

# 7. Public API Design

The MVP public API should be small and pleasant.

Target usage:

```python
from agentproof import AgentTest, World, invariant
from agentproof.mutations import standard_reliability_pack

suite = AgentTest(
    agent=my_agent,
    adapter="native",
    mutations=standard_reliability_pack(),
)

@suite.scenario
async def refund_delivered_order(world: World):
    world.state.orders["123"] = {
        "id": "123",
        "total": 49.0,
        "status": "delivered",
    }

    world.input("Refund order 123")


@invariant
def no_double_refunds(world: World):
    assert world.effects.sum(
        type="refund.created",
        where={"order_id": "123"},
        field="amount",
    ) <= 49.0
```

It is acceptable for implementation details to differ slightly if the resulting API is cleaner, but keep the number of concepts small.

Public MVP names:

- `AgentTest`
- `World`
- `Scenario`
- `invariant`
- `Mutation`
- `Effect`
- `TraceEvent`
- `TestResult`
- built-in invariant helpers
- mutation pack helpers

Avoid exposing internal registries/controllers unless necessary.

---

# 8. Core Data Models

Use Pydantic models or frozen dataclasses where serialization matters.

## 8.1 Effect

```python
class Effect(BaseModel):
    id: str
    type: str
    tool_name: str
    operation: str | None = None
    resource: str | None = None
    data: dict[str, Any]
    committed_at: float
    idempotency_key: str | None = None
    invocation_id: str
```

Examples:

- `refund.created`
- `email.sent`
- `calendar.event_created`
- `file.deleted`

## 8.2 TraceEvent

```python
class TraceEvent(BaseModel):
    seq: int
    timestamp: float
    kind: Literal[
        "user_input",
        "tool_call",
        "tool_result",
        "tool_error",
        "effect",
        "fault",
        "state_change",
        "agent_output",
        "invariant_pass",
        "invariant_fail",
    ]
    name: str
    data: dict[str, Any]
```

## 8.3 MutationSpec

All mutations must be serializable:

```python
class MutationSpec(BaseModel):
    type: str
    target: str | None
    occurrence: int | None = 1
    params: dict[str, Any] = {}
    severity: Literal["low", "medium", "high", "critical"] = "medium"
```

## 8.4 RunArtifact

Persist enough data to reproduce deterministic failures:

```python
class RunArtifact(BaseModel):
    schema_version: int
    run_id: str
    scenario: str
    seed: int
    mutation: MutationSpec | None
    initial_world_snapshot: dict[str, Any]
    trace: list[TraceEvent]
    violated_invariants: list[str]
    metadata: dict[str, Any]
```

Do not serialize API keys, secrets, raw authorization headers, or environment variables.

---

# 9. `World` Specification

`World` is the core stateful simulation environment.

Minimum capabilities:

```python
class World:
    state: StateStore
    tools: ToolRegistry
    effects: EffectLedger
    events: EventQueue
    clock: VirtualClock
    trace: TraceRecorder
    faults: FaultController
    metadata: dict[str, Any]

    def input(self, text: str) -> None: ...
    def snapshot(self) -> dict[str, Any]: ...
    def clone_from_initial(self) -> "World": ...
```

## 9.1 StateStore

It may initially be dictionary-backed. It must:

- deep-copy cleanly;
- serialize to JSON-safe values when possible;
- support explicit mutation logging;
- avoid hidden shared mutable objects between runs.

Do not over-engineer a database abstraction.

## 9.2 VirtualClock

The clock must not monkeypatch global time in MVP.

Expose:

```python
world.clock.now()
world.clock.advance(seconds=30)
```

Tools and event queue should use this clock where appropriate.

## 9.3 EventQueue

Support scheduling and deterministic delivery:

```python
world.events.schedule(
    name="shipment.updated",
    payload={...},
    delay=10,
)
```

MVP only needs enough event behavior to test delayed and duplicate events.

---

# 10. Virtual Tool Model

A virtual tool must preserve the schema/name visible to the agent while routing execution to AgentProof-controlled code.

Suggested definition:

```python
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any] | Any]
    effect: Literal["read", "write", "delete", "external", "financial", "privileged"] | None
    idempotent: bool | None
```

## 10.1 Invocation lifecycle

Every tool invocation must follow an explicit lifecycle:

```text
RECEIVE CALL
  -> trace tool_call
  -> apply pre-call mutation if any
  -> execute virtual handler
  -> commit domain state/effects
  -> apply post-commit/pre-response mutation if any
  -> return result OR raise visible fault
  -> trace result/error
```

This lifecycle is what makes ambiguous failures possible.

## 10.2 Commit boundary

Create an internal distinction such as:

```python
ToolOutcome(
    value=...,
    effects=[...],
    committed=True,
)
```

`TimeoutAfterCommit` must allow effects/state to remain committed while converting the observable result to a timeout exception.

## 10.3 Idempotency support

The refund demo must include a virtual service that can optionally enforce idempotency keys:

```python
refund_order(order_id, amount, idempotency_key=None)
```

If an idempotency key already produced a refund, return the original refund without creating another effect.

---

# 11. Mutation Engine

## 11.1 MVP mutation set

Implement and test these first:

1. `ToolTimeout`
2. `TimeoutAfterCommit`
3. `ToolError`
4. `ToolLatency`
5. `RateLimited`
6. `MalformedResponse`
7. `MissingField`
8. `DuplicateUserRequest`
9. `DuplicateToolResult`
10. `StaleState`
11. `StateChangedAfterRead`
12. `ReorderToolResults`
13. `PermissionDenied`
14. `DelayedEvent`
15. `DuplicateEvent`

If `ReorderToolResults` proves too invasive for the first adapter version, it may be marked experimental, but it must not be presented as stable until tested.

## 11.2 Mutation protocol

```python
class Mutation(Protocol):
    spec: MutationSpec

    def install(self, world: World) -> None: ...
```

Prefer composable hooks managed by `FaultController` rather than every mutation monkeypatching arbitrary functions.

Possible hook stages:

- `before_tool_call`
- `after_handler_before_commit`
- `after_commit_before_response`
- `after_tool_response`
- `before_agent_input`
- `on_event_delivery`

## 11.3 Standard reliability pack

Expose:

```python
standard_reliability_pack()
```

This should generate sensible single-fault mutations for every matching virtual tool based on tool metadata.

Example:

- read tool: latency, timeout, tool error, malformed response, missing field;
- write tool: all above plus timeout-after-commit;
- non-idempotent write tool: duplicate invocation/high priority;
- financial tool: high severity for duplicate side effects.

## 11.4 Mutation combinations

**Do not implement automatic pairwise/combinatorial exploration in MVP unless core scope finishes early.**

The architecture should permit multiple installed mutations, but default execution should use mutation depth 1.

---

# 12. Invariant Engine

## 12.1 Decorator

```python
@invariant
def no_double_refunds(world: World):
    ...
```

Support both sync and async invariant functions if inexpensive.

## 12.2 Failure capture

Convert assertion failures into structured results with:

- invariant name;
- assertion message;
- exception type;
- short traceback pointing to user invariant code;
- world/effect summary;
- mutation context.

Do not swallow non-assertion programming errors; distinguish `test_error` from `invariant_failure`.

## 12.3 Built-in invariants

Implement useful helpers:

```python
invariants.at_most_once(tool_name)
invariants.max_tool_calls(tool_name, count)
invariants.never_call(tool_name)
invariants.requires_before(required_tool, action_tool)
invariants.max_effect_sum(effect_type, field, maximum)
invariants.no_duplicate_effects(effect_type, key_fields=[...])
invariants.forbid_resource(resource_pattern)
```

Keep them deterministic.

---

# 13. Agent Adapter Protocol

Core runner should interact with all agents through a minimal protocol.

Suggested protocol:

```python
class AgentAdapter(Protocol):
    name: str

    async def run(
        self,
        *,
        world: World,
        user_input: str,
    ) -> AgentRunResult:
        ...
```

`AgentRunResult` should contain at least:

- final output;
- adapter/framework metadata;
- model metadata when available;
- raw framework result only as optional non-serialized debug information.

The adapter is responsible for exposing AgentProof virtual tools to the specific framework.

---

# 14. Native Python Adapter

Build this first.

Support a callable agent with a signature like:

```python
async def agent(user_input: str, tools: ToolClient) -> str:
    ...
```

or an adapter wrapper around arbitrary callables.

The goal is not to invent another agent framework; this adapter exists to test the AgentProof engine without external dependencies and to support custom homegrown loops.

Unit/integration tests should use this adapter extensively.

---

# 15. OpenAI Agents SDK Adapter

Use the current official OpenAI Agents SDK Python package.

Current official architecture uses `Agent`, `Runner`, and function tools. Function tools expose a controlled invocation callback (`FunctionTool.on_invoke_tool`) and the SDK can execute an agent via `Runner.run`, `run_sync`, or `run_streamed`.

Official references at time of this specification:

- https://openai.github.io/openai-agents-python/
- https://openai.github.io/openai-agents-python/tools/
- https://openai.github.io/openai-agents-python/running_agents/

## 15.1 Adapter goal

Given virtual AgentProof tools, construct SDK-visible `FunctionTool` objects with:

- same name;
- same description;
- same JSON input schema;
- `on_invoke_tool` callback routed through `world.tools.invoke(...)`.

Do not call the user's original production tool implementation.

## 15.2 Example

AgentProof virtual tool:

```python
world.tools.register(
    name="refund_order",
    description="Refund a delivered order.",
    input_schema={...},
    handler=virtual_refund,
    effect="financial",
    idempotent=False,
)
```

Adapter should produce an OpenAI SDK `FunctionTool` that delegates to AgentProof.

## 15.3 Real SDK integration test without live model

Where possible, test construction/invocation of the actual `FunctionTool` object directly through the SDK callback path, validating schema and return/error semantics.

This proves compatibility without spending tokens.

## 15.4 Live OpenAI end-to-end test

Create a test marked:

```python
@pytest.mark.live
@pytest.mark.openai
```

Skip unless:

```text
OPENAI_API_KEY is set
AGENTPROOF_RUN_LIVE_TESTS=1
```

The test must:

1. instantiate a real OpenAI SDK `Agent`;
2. expose `get_order` and `refund_order` as AgentProof-wrapped SDK tools;
3. run with `Runner.run(...)`;
4. execute a baseline successfully;
5. execute the `timeout_after_commit` mutation;
6. not assert that a stochastic model must always retry unless the prompt/agent logic makes retry deterministic enough;
7. instead, record whether the real agent safely handles ambiguous timeout and validate final world invariants;
8. store a sanitized trace artifact on failure.

For a stable regression test, implement a deliberately naive retry policy around the SDK agent/tool interaction if necessary, but clearly label which behavior is deterministic framework logic vs. model-decided behavior.

## 15.5 Safety

Live tests must only call OpenAI model APIs. All action tools remain local virtual tools. No real Stripe/Gmail/cloud calls.

---

# 16. LangChain/LangGraph Adapter

Use current LangChain v1 / LangGraph APIs. Current LangChain `create_agent` runs on LangGraph; current LangGraph supports `ToolNode` for tool execution. `create_react_agent` is deprecated in LangGraph v1 in favor of `langchain.agents.create_agent`.

Official references at time of specification:

- https://docs.langchain.com/oss/python/langchain/agents
- https://docs.langchain.com/oss/python/langchain/tools
- https://docs.langchain.com/oss/python/langgraph/quickstart
- https://docs.langchain.com/oss/python/migrate/langgraph-v1

## 16.1 Adapter goal

Support a normal LangChain/LangGraph agent using AgentProof virtual tools.

Preferred implementation:

- create framework tool functions/objects whose body delegates to `world.tools.invoke`;
- pass those tools to `langchain.agents.create_agent` or a user graph;
- avoid monkeypatching LangGraph internals.

## 16.2 Real integration test without live LLM

Test real LangChain tool wrappers and, if practical, a small compiled `StateGraph`/`ToolNode` using a deterministic fake model/message sequence so the actual LangGraph execution machinery is exercised.

## 16.3 Live model test

Mark separately:

```python
@pytest.mark.live
@pytest.mark.langchain
```

Skip unless explicit environment flags/credentials are present.

Use an OpenAI-backed LangChain model only if configured, or support provider selection through environment variables. Do not make live LangChain tests required for package correctness.

---

# 17. Scenario Runner

Core runner algorithm:

```text
1. load scenario definition
2. build pristine baseline world
3. execute baseline
4. evaluate invariants
5. if baseline itself fails -> report BASELINE_FAILURE and do not claim mutation discovery
6. enumerate eligible single mutations
7. for each mutation:
      a. create fresh world from initial scenario setup
      b. install exactly that mutation
      c. run same agent input
      d. collect tool calls/effects/trace
      e. evaluate invariants
      f. persist failure artifact if needed
8. aggregate results
9. render report
10. return exit code based on policy
```

## 17.1 Isolation test

Add a test proving:

- mutation run A can modify state;
- mutation run B starts with pristine initial state;
- baseline rerun remains pristine.

## 17.2 Repetitions

Support:

```bash
agentproof run --repetitions 5
```

For stochastic agents, aggregate:

- pass count;
- fail count;
- observed failure rate.

Do not present this as a statistically rigorous probability estimate in MVP; call it **observed failure rate across N runs**.

---

# 18. Replay

## 18.1 Command

```bash
agentproof replay path/to/repro.json
```

## 18.2 MVP replay guarantee

Replay is guaranteed for:

- deterministic/native agent examples;
- recorded mutation specification;
- AgentProof-controlled tool behavior;
- initial state snapshot.

For live LLM agents, exact model output cannot be guaranteed. Therefore implement two modes conceptually:

### `live`
Rerun the real agent/model with the same mutation and seed.

### `tool-replay` (MVP optional if difficult)
Replay a recorded sequence at the tool boundary to reproduce environment/effect behavior without depending on another model call.

Do not claim exact deterministic LLM replay unless it is actually implemented.

## 18.3 Artifact schema versioning

Every reproduction artifact must contain a schema version.

---

# 19. Failure Minimization / Shrinking

Full property-based shrinking is **not required for the first publishable MVP**, but implement a minimal mutation shrinker:

- if a failure occurs under a single mutation, the minimal mutation is already known;
- if future multi-mutation tests are manually supplied, attempt removal of one mutation at a time while preserving the failure.

Expose this as experimental only.

Do not implement a fake “AI shrinker.”

---

# 20. CLI Specification

Use Typer or Click.

## 20.1 `agentproof init`

Creates:

```text
agentproof.toml
.agentproof/
tests/agentproof/
```

Do not overwrite existing files without confirmation/`--force`.

## 20.2 `agentproof run`

Options:

```text
agentproof run [PATH]
  --scenario NAME
  --mutation NAME
  --cases N
  --repetitions N
  --seed INT
  --fail-on [low|medium|high|critical]
  --json PATH
  --junit PATH
  --no-color
  --verbose
```

If `--cases` is retained, define it clearly; otherwise omit until property-based generation exists. Prefer fewer honest flags.

## 20.3 `agentproof mutations`

List registered mutation types and one-line descriptions.

## 20.4 `agentproof replay`

Rerun a reproduction artifact.

## 20.5 `agentproof doctor`

Optional but useful. Validate:

- Python version;
- installed optional adapter dependencies;
- config parsing;
- writable `.agentproof` directory.

Do not validate API keys by making remote calls unless requested.

---

# 21. Configuration

Use TOML.

Example:

```toml
[agentproof]
seed = 42
repetitions = 1
parallelism = 1
fail_on = "high"
artifacts_dir = ".agentproof/runs"

[mutations]
depth = 1
include = ["standard"]

[reporting]
store_traces = true
```

MVP runner may remain sequential. If parallelism is not implemented safely, keep `parallelism = 1` and do not advertise parallel execution.

---

# 22. Terminal Reporting

Use Rich or equivalent.

A failure report must contain:

- scenario;
- adapter/framework;
- baseline status;
- mutation name;
- target tool/event;
- violated invariant;
- expected/observed message where available;
- side-effect summary;
- compact ordered trace;
- reproduction artifact path;
- seed;
- severity.

Avoid vanity scores such as “97% safe.”

Report concrete counts:

```text
16 runs
14 passed
2 failed
1 high
1 medium
```

---

# 23. JSON and JUnit Reporting

## 23.1 JSON

Output stable structured test results with schema version.

## 23.2 JUnit XML

Create one testcase per scenario+mutation run, so CI systems can display failures.

Invariant violation -> failed testcase.  
Framework/setup error -> error testcase.  
Skipped unsupported mutation -> skipped testcase.

---

# 24. Pytest Integration

Provide a useful but lightweight pytest plugin.

Potential MVP features:

- marker registration (`agentproof`, `live`);
- command-line option to show/store AgentProof artifacts;
- fixture for temporary AgentProof artifact directory;
- optional helper to execute a suite inside a pytest test.

Do not invent a custom collection model unless it materially improves UX.

The normal AgentProof SDK/CLI should work independently of pytest.

Verify plugin discovery via Pytest's `pytest11` entry point.

---

# 25. Testing Strategy

Testing is a first-class deliverable.

## 25.1 Unit tests

Must cover at least:

### World
- pristine snapshot creation;
- deep isolation;
- state mutation recording;
- virtual clock;
- event scheduling.

### Effects
- effect append;
- filtering;
- aggregate sum;
- duplicate detection;
- idempotency metadata.

### Tools
- normal invocation;
- sync handler;
- async handler;
- validation error;
- effect commit;
- handler exception.

### Mutations
Each mutation gets at least one direct unit test.

`TimeoutAfterCommit` must specifically prove:

```text
effect exists == True
caller observed timeout == True
```

### Invariants
- pass;
- fail;
- unexpected exception classified as error;
- built-in invariant helpers.

### Trace
- event ordering;
- serializability;
- sensitive metadata redaction.

### Replay
- artifact encode/decode;
- schema mismatch behavior;
- deterministic reproduction.

## 25.2 Integration tests

Must cover:

1. native refund baseline;
2. native refund double-refund detection;
3. idempotent refund fix passes;
4. CLI run exit 0 on pass;
5. CLI run exit nonzero on configured failure;
6. JSON reporter;
7. JUnit reporter;
8. pytest plugin registration;
9. actual OpenAI Agents SDK wrapper/invocation path;
10. actual LangChain/LangGraph tool execution path.

## 25.3 E2E live tests

Never run by default.

Command:

```bash
AGENTPROOF_RUN_LIVE_TESTS=1 pytest -m live -v
```

They must be skipped otherwise.

## 25.4 Coverage

Target >=90% coverage for core package initially, but do not game coverage with meaningless tests.

Use branch coverage if practical.

---

# 26. Required Example Projects

## 26.1 `examples/refund_native`

Contains:

- world setup;
- naive agent;
- safe/idempotent agent;
- standard mutation run;
- expected reproduction.

This is the deterministic golden example.

## 26.2 `examples/refund_openai_agents`

Contains:

- actual OpenAI `Agent`;
- AgentProof-generated SDK function tools;
- baseline command;
- live command requiring `OPENAI_API_KEY`;
- no real external side effects.

## 26.3 `examples/refund_langchain`

Contains:

- actual `langchain.agents.create_agent` or current equivalent;
- AgentProof-routed tools;
- documented live execution path.

## 26.4 `examples/calendar_native`

Demonstrate a different action type:

- `create_calendar_event` commits;
- response timeout;
- retry causes duplicate event;
- invariant detects duplicate meeting.

This proves AgentProof is not refund-specific.

---

# 27. Real-Agent Validation Plan

The framework is not ready to publish based solely on mocked agents.

Before release, perform these validation levels.

## Level A — deterministic native agent

Purpose: prove AgentProof engine semantics.

Required result:

- baseline passes;
- timeout-after-commit finds double refund;
- replay reproduces;
- idempotency fix passes.

## Level B — actual OpenAI Agents SDK objects, local execution boundary

Purpose: prove adapter compatibility.

Required result:

- actual SDK `FunctionTool` objects are constructed;
- SDK invocation callback routes to AgentProof;
- schema is preserved;
- timeout/error propagates as expected;
- no production tool executes.

## Level C — actual LangChain/LangGraph execution graph

Purpose: prove second framework compatibility.

Required result:

- actual LangChain/LangGraph tool node/agent executes AgentProof tools;
- mutation reaches framework agent as a realistic tool failure;
- trace captures the tool interaction.

## Level D — live LLM agent

Purpose: demonstrate real autonomous decision behavior.

Run the OpenAI example with a small/low-cost currently supported model selected through configuration/environment.

Record:

- model identifier;
- framework version;
- prompt hash;
- mutation;
- final world state;
- invariant result;
- token/cost metadata if framework exposes it.

Do not hardcode a model name that may disappear. Allow:

```text
AGENTPROOF_OPENAI_MODEL=<model>
```

with a sensible documented default chosen at implementation time from currently supported models.

## Level E — one external sample agent/repository

Before public launch, integrate AgentProof into at least one separate sample agent project (can be a small dedicated public fixture repo) rather than only examples inside the AgentProof repository.

Goal:

> prove integration friction is acceptable for code AgentProof did not author internally.

Document exact setup steps and time/LOC required.

---

# 28. Security and Safety Requirements

## 28.1 No real side effects by default

AgentProof examples/tests must never:

- charge/refund real money;
- send real email/SMS;
- modify real cloud resources;
- delete user files outside temporary test directories;
- mutate real GitHub repositories.

## 28.2 Secret redaction

Trace/report serialization must redact obvious secret keys by key name, including patterns such as:

- `api_key`
- `authorization`
- `token`
- `password`
- `secret`

Do not claim comprehensive DLP. Document that developers remain responsible for sensitive tool payloads.

## 28.3 Artifact permissions

When possible, create `.agentproof` artifacts with user-only writable defaults.

## 28.4 Threat model document

`SECURITY.md` or `docs/security.md` should state:

- AgentProof executes developer-provided Python code during tests;
- it is not a sandbox for untrusted code;
- it should run with least-privilege credentials;
- real tools should be replaced by virtual tools;
- live LLM tests may send prompts/tool schemas to the configured model provider.

---

# 29. Code Quality Standards

Use:

- `ruff` for formatting/linting;
- `mypy` (or Pyright if repository owner chooses) for type checking;
- `pytest`;
- `pytest-asyncio` if needed;
- `pytest-cov`;
- `build` for wheel/sdist build;
- `twine check` for distribution validation.

Commands should eventually pass:

```bash
ruff format --check .
ruff check .
mypy src/agentproof
pytest -q
python -m build
twine check dist/*
```

Do not suppress broad lint/type errors merely to get green CI.

---

# 30. CI Workflow

Create `.github/workflows/ci.yml`.

On pull request/push:

1. checkout;
2. set up Python matrix;
3. install package with test/dev extras;
4. ruff format check;
5. ruff lint;
6. type check;
7. unit + integration tests excluding live marker;
8. build distribution on one matrix job;
9. run `twine check`;
10. optionally install built wheel into a fresh environment and execute smoke test.

Live LLM tests must not run on normal PRs.

Optionally support a manually triggered workflow for live tests if secrets are configured.

---

# 31. Release / PyPI Workflow

Use PyPI Trusted Publishing through GitHub Actions rather than long-lived API tokens.

Official references:

- https://docs.pypi.org/trusted-publishers/using-a-publisher/
- https://docs.pypi.org/trusted-publishers/adding-a-publisher/

Create `.github/workflows/release.yml` with:

- trigger on GitHub Release published OR version tag, choose one clearly;
- build job;
- artifact upload/download separation;
- publish job using PyPA publish action;
- environment named `pypi`;
- `id-token: write` only for publish job;
- minimal other permissions.

Do not store PyPI passwords/tokens in repo.

Recommended owner setup before first real publish:

1. create/claim PyPI project name or pending publisher;
2. configure Trusted Publisher for exact GitHub owner/repo/workflow filename;
3. protect `pypi` environment with manual approval if desired;
4. publish release candidate to TestPyPI first if practical;
5. install published/TestPyPI artifact in clean environment;
6. only then perform production PyPI publish.

The PyPI security documentation recommends restricting publishing trust to the exact repository/workflow and keeping release workflow privileges narrow.

---

# 32. Versioning

Use Semantic Versioning pragmatically.

Initial public version:

```text
0.1.0
```

Pre-release can use:

```text
0.1.0a1
```

Public API may change before 1.0, but document breaking changes in `CHANGELOG.md`.

Package should expose:

```python
from agentproof import __version__
```

Prefer generated package metadata rather than maintaining duplicate manual version strings when possible.

---

# 33. README Requirements

README must be developer-first.

Required structure:

1. product one-liner;
2. 20–30 line terminal/demo output showing double refund detection;
3. installation;
4. five-minute quickstart;
5. core concepts: world, tool, mutation, effect, invariant;
6. supported mutations;
7. supported integrations;
8. replay;
9. CI usage;
10. project status/limitations;
11. contributing;
12. license.

Avoid claims like “guarantees agent safety.”

Preferred wording:

> AgentProof helps discover and regression-test action-level failures under simulated environment faults. It does not prove an agent is universally safe or correct.

---

# 34. Five-Minute Quickstart API

The final API can differ slightly, but README should allow something similar to:

```python
from agentproof import AgentTest, World, invariant
from agentproof.adapters.native import NativeAdapter
from agentproof.mutations import TimeoutAfterCommit


async def refund_agent(user_input, tools):
    order = await tools.call("get_order", order_id="123")
    try:
        await tools.call(
            "refund_order",
            order_id="123",
            amount=order["total"],
        )
    except TimeoutError:
        # deliberately unsafe retry for demo
        await tools.call(
            "refund_order",
            order_id="123",
            amount=order["total"],
        )
    return "Done"


suite = AgentTest(
    agent=refund_agent,
    adapter=NativeAdapter(),
    mutations=[TimeoutAfterCommit(target="refund_order")],
)


@suite.scenario
async def delivered_refund(world: World):
    world.state["orders"] = {
        "123": {"id": "123", "status": "delivered", "total": 49.0}
    }
    world.input("Refund order 123")


@invariant
def never_over_refund(world: World):
    total = world.effects.sum(
        type="refund.created",
        where={"order_id": "123"},
        field="amount",
    )
    assert total <= 49.0, f"refunded ${total:.2f}, expected <= $49.00"
```

Then:

```bash
agentproof run tests/agentproof
```

The exact discovery mechanism should be simple and documented.

---

# 35. Golden Acceptance Tests

These are release blockers.

## AT-001 Baseline refund

Given delivered order $49, normal refund path creates exactly one $49 effect and passes.

## AT-002 Timeout before commit

Tool timeout happens before handler commit. No refund effect exists. Agent retry creates one $49 refund. Invariant passes.

## AT-003 Timeout after commit

First refund effect commits, caller receives timeout, unsafe retry creates second refund. Invariant fails with $98 observed.

## AT-004 Idempotency fix

Same test using idempotency key results in exactly one $49 committed refund despite retry. Invariant passes.

## AT-005 Reproduction

The deterministic `AT-003` failure writes a repro artifact. `agentproof replay` reproduces the invariant failure and equivalent effect sequence.

## AT-006 Isolation

Running AT-003 followed by AT-001 does not carry over refunds.

## AT-007 Error vs invariant

A bug in test setup is reported as framework/test error, not an invariant failure.

## AT-008 CLI status

Failing high-severity mutation exits nonzero when `--fail-on high`.

## AT-009 JSON schema

JSON output parses and includes scenario, seed, mutation, trace, and invariant failure.

## AT-010 JUnit

JUnit output is accepted by an XML parser and represents failure correctly.

## AT-011 OpenAI SDK local adapter

Actual installed OpenAI Agents SDK `FunctionTool` invocation delegates to AgentProof tool registry.

## AT-012 LangChain/LangGraph local adapter

Actual installed framework tool/graph execution delegates to AgentProof tool registry.

## AT-013 Live OpenAI agent (manual)

With credentials and explicit live flag, a real SDK agent runs against AgentProof virtual tools and produces a stored result without any real external side effect.

## AT-014 Wheel smoke test

Build wheel, install into a newly created clean virtual environment, run quickstart/smoke test successfully.

---

# 36. Mutation-Specific Acceptance Tests

Every stable mutation must demonstrate exactly what changed.

## ToolTimeout

- handler does not commit if defined as pre-call timeout;
- caller receives timeout.

## TimeoutAfterCommit

- handler/effects commit;
- caller receives timeout;
- trace orders EFFECT before FAULT/tool error.

## ToolError

- configured exception surfaced;
- no unconfigured side effects.

## ToolLatency

- virtual clock advances or recorded latency is visible;
- test does not sleep for long real durations.

## RateLimited

- caller receives typed/recognizable rate-limit failure.

## MalformedResponse

- response transformation is deterministic and serializable.

## MissingField

- only configured field is removed.

## DuplicateUserRequest

- same user intent delivered twice through defined semantics.

## DuplicateToolResult

- framework-specific limitations documented;
- only stable if semantics are testable.

## StaleState

- read returns an older snapshot while canonical state differs.

## StateChangedAfterRead

- state changes after configured read occurrence but before later write/action.

## ReorderToolResults

- only enable for actual concurrent/parallel tool execution paths that can be controlled.

## PermissionDenied

- caller receives permission failure; no effect commits.

## DelayedEvent

- event is delivered only after virtual clock threshold.

## DuplicateEvent

- same event payload delivered configured number of times with distinct delivery trace events.

---

# 37. Failure Taxonomy

Use consistent result categories:

```text
PASS
INVARIANT_FAILURE
BASELINE_FAILURE
AGENT_ERROR
TOOL_ERROR_EXPECTED
TEST_ERROR
ADAPTER_ERROR
UNSUPPORTED
SKIPPED
```

A deliberately injected tool fault itself is not a test failure. It becomes a failure only if it causes an invariant violation or violates an explicit expectation.

---

# 38. Severity

Mutations/invariants may have severity:

```text
low
medium
high
critical
```

Do not automatically infer “critical” merely because AI is involved.

Suggested defaults:

- duplicate financial effect: high;
- production delete invariant: critical;
- duplicate calendar event: medium;
- malformed read response safely handled: pass.

Allow user override.

---

# 39. Observability and Trace Semantics

Trace should answer:

> What did the user ask, what tool did the agent call, what did the simulated world do, what fault did AgentProof inject, what side effects committed, what did the agent do next, and which invariant failed?

Trace should not depend on exposing hidden model chain-of-thought. Record observable actions/events only.

If a framework provides reasoning summaries or messages as normal outputs, they may be stored optionally, but AgentProof must not require hidden reasoning access.

---

# 40. Determinism Rules

AgentProof-controlled behavior must be deterministic given:

- initial world snapshot;
- mutation spec;
- random seed;
- virtual clock schedule.

Use a dedicated `random.Random(seed)` instance instead of process-global randomness.

Do not depend on dictionary iteration order as an intended randomization mechanism.

LLM behavior is explicitly outside this determinism guarantee.

---

# 41. Performance Requirements

MVP target:

- framework overhead for local deterministic tests should be small relative to model calls;
- no mutation should sleep for seconds of wall-clock time to simulate latency;
- a suite of 100 local deterministic mutation runs should complete reasonably fast on a laptop;
- artifact storage should be bounded/configurable.

Do not optimize prematurely, but avoid obvious O(N²) trace operations where N can grow significantly.

---

# 42. Backward Compatibility / Extensibility

Internal mutation hooks and serialized schemas should include version identifiers where needed.

Adapters should be discoverable/constructible without hardcoding every framework into core runtime.

However, do not build a plugin marketplace system for MVP.

---

# 43. Explicit Non-Goals for v0.1

Do **not** build these before the core release criteria are satisfied:

- web dashboard;
- cloud-hosted test runner;
- billing;
- auth/RBAC;
- team collaboration;
- prompt playground;
- LLM-as-a-judge scoring;
- automatic prompt optimization;
- MCP security scanner;
- comprehensive browser sandbox;
- real payment sandbox integration;
- arbitrary production traffic replay;
- massive synthetic user simulator;
- formal verification;
- distributed parallel runner;
- automatic pairwise/3-way mutation search;
- custom model gateway;
- TypeScript SDK.

Create GitHub issues/roadmap entries instead if useful.

---

# 44. Implementation Phases

## Phase 1 — repository and quality foundation

Deliver:

- package skeleton;
- pyproject;
- lint/type/test tooling;
- CI skeleton;
- core result models;
- empty public API with documented roadmap.

Gate:

```bash
ruff check .
mypy src/agentproof
pytest
python -m build
```

all pass.

## Phase 2 — deterministic world and tools

Deliver:

- World;
- StateStore;
- ToolRegistry;
- EffectLedger;
- Trace;
- virtual clock;
- native adapter.

Gate: baseline refund works.

## Phase 3 — invariants and runner

Deliver:

- scenario lifecycle;
- invariant decorator/engine;
- pristine world rebuilding;
- structured results.

Gate: baseline pass + intentionally over-refunded world fail.

## Phase 4 — core fault injection

Implement first five:

- timeout;
- timeout-after-commit;
- error;
- latency;
- rate limit.

Gate: killer double-refund demo passes acceptance tests.

## Phase 5 — replay and reporting

Deliver:

- repro artifact;
- replay CLI;
- terminal reporter;
- JSON/JUnit.

Gate: deterministic reproduction confirmed.

## Phase 6 — remaining MVP mutations

Implement/test remaining stable mutations.

Gate: each has direct automated test.

## Phase 7 — OpenAI Agents SDK adapter

Deliver optional extra + example + local SDK compatibility tests + manual live test.

Gate: AT-011 and optional AT-013.

## Phase 8 — LangChain/LangGraph adapter

Deliver optional extra + example + real framework graph/tool integration tests.

Gate: AT-012.

## Phase 9 — pytest and CI UX

Deliver pytest entry point, CLI polish, CI integration.

## Phase 10 — packaging/release readiness

Deliver:

- README;
- docs;
- license;
- contribution docs;
- changelog;
- wheel/sdist checks;
- clean-env smoke install;
- release workflow.

No real publication until owner authorization.

---

# 45. Codex Completion Checklist

Do not declare the project complete until you can answer **yes** to each item.

## Core

- [ ] `World` exists and is isolated per run.
- [ ] Virtual tools can read/write state.
- [ ] Effect ledger records committed external-style actions.
- [ ] Commit and response phases are separated.
- [ ] Invariants are deterministic.
- [ ] Runner executes baseline and mutations.
- [ ] Seed is persisted.
- [ ] Trace is ordered and human-readable.

## Faults

- [ ] Timeout before commit works.
- [ ] Timeout after commit works.
- [ ] Tool error works.
- [ ] Latency simulation avoids long sleep.
- [ ] Rate limit works.
- [ ] Malformed response works.
- [ ] Missing field works.
- [ ] Duplicate user request works.
- [ ] Stale state works.
- [ ] State changed after read works.
- [ ] Permission denied works.
- [ ] Delayed event works.
- [ ] Duplicate event works.
- [ ] Any advertised ordering/duplicate-result mutations are genuinely tested.

## Integrations

- [ ] Native adapter works.
- [ ] OpenAI Agents SDK optional extra works.
- [ ] LangChain/LangGraph optional extra works.
- [ ] Real SDK/framework objects are used in integration tests.
- [ ] Live LLM tests are opt-in only.

## Developer UX

- [ ] CLI install works.
- [ ] `agentproof run` works.
- [ ] `agentproof mutations` works.
- [ ] `agentproof replay` works.
- [ ] Error messages are actionable.
- [ ] README quickstart can be copied into a clean repo.

## CI/release

- [ ] Ruff passes.
- [ ] Mypy passes.
- [ ] Tests pass.
- [ ] Coverage target met reasonably.
- [ ] Wheel/sdist build.
- [ ] `twine check` passes.
- [ ] Wheel installs in clean environment.
- [ ] Pytest plugin is discovered.
- [ ] GitHub CI works.
- [ ] Trusted Publishing workflow exists with least privileges.

## Truthfulness

- [ ] README does not claim unsupported mutations.
- [ ] README does not claim universal agent safety.
- [ ] No mocked test is described as a live-agent test.
- [ ] No real side-effect service is invoked by examples/tests.
- [ ] Known limitations are documented.

---

# 46. Pre-Publication Validation Report

Before release, generate `docs/release-validation-0.1.0.md` containing actual command outputs/results (summarized, not fabricated):

```text
Python versions tested:
OS tested:
Core unit tests:
Integration tests:
Coverage:
OpenAI Agents SDK version:
OpenAI adapter local compatibility result:
OpenAI live test result (if run):
LangChain version:
LangGraph version:
LangChain/LangGraph adapter result:
Wheel clean-install result:
Known limitations:
```

Include a table of mutations with:

```text
Mutation | Unit tested | Integration tested | Adapter coverage | Stable/experimental
```

Do not mark something stable without evidence.

---

# 47. Suggested GitHub Issues After v0.1

Create roadmap issues, but do not block release on them:

1. pairwise mutation exploration;
2. property-based scenario inputs via Hypothesis;
3. delta-debugging/shrinking;
4. production trace -> scenario conversion;
5. MCP adapter;
6. coding-agent filesystem world;
7. browser-agent environment adapter;
8. policy DSL / YAML reliability specification;
9. automatic tool risk classification;
10. mutation packs by domain (payments, calendar, CRM, DevOps);
11. statistical repeated-run analysis;
12. hosted/team result dashboard;
13. TypeScript SDK.

---

# 48. Architecture Decision: Why This Is Different

Preserve this distinction in implementation and docs:

```text
Traditional agent eval
    prompt/input
       -> agent
       -> output/trajectory
       -> score

AgentProof
    initial world state
       -> real agent
       -> virtual tools
       -> committed side effects
       -> injected environment fault
       -> agent reaction/retry
       -> final world state
       -> deterministic invariant
```

AgentProof's differentiator is not merely that it watches tool calls. It creates and controls **stateful tool semantics**, including failures where the external operation and the agent's observation disagree.

If the implementation drifts into a generic response-evaluation library, stop and correct course.

---

# 49. Minimal Internal Architecture Diagram

```text
                     AgentTest / Scenario
                            |
                            v
                       ScenarioRunner
                            |
              +-------------+-------------+
              |                           |
              v                           v
          AgentAdapter                  World
              |                           |
              |                 +---------+----------+
              |                 |         |          |
              v                 v         v          v
        Real Agent Loop      State      Tools      Events
                                |         |
                                |         v
                                |    FaultController
                                |         |
                                |         v
                                |    Virtual Handler
                                |         |
                                |      COMMIT
                                |         |
                                |         v
                                +---- EffectLedger
                                          |
                                          v
                                         Trace
                                          |
                                          v
                                   InvariantEngine
                                          |
                                          v
                                      TestResult
                                          |
                         +----------------+----------------+
                         v                v                v
                      Console            JSON            JUnit
                                          |
                                          v
                                    Repro Artifact
```

---

# 50. Example `TimeoutAfterCommit` Pseudocode

This behavior is central enough to specify explicitly.

```python
async def invoke_tool(name: str, args: dict[str, Any]) -> Any:
    invocation_id = new_id()
    trace.tool_call(name, args, invocation_id)

    fault = faults.match(
        stage="before_tool_call",
        tool=name,
        invocation=invocation_id,
    )
    if fault:
        return fault.raise_or_transform(...)

    outcome = await tool.handler(**args)

    # Commit state/effects first.
    commit(outcome)
    trace.effects(outcome.effects)

    fault = faults.match(
        stage="after_commit_before_response",
        tool=name,
        invocation=invocation_id,
    )

    if isinstance(fault, TimeoutAfterCommit):
        trace.fault("timeout_after_commit", ...)
        trace.tool_error(name, "TimeoutError", ...)
        raise ToolTimeoutError(name)

    trace.tool_result(name, outcome.value, ...)
    return outcome.value
```

The actual design may use context managers/hooks, but this ordering must be preserved.

---

# 51. Example Release-Quality Test for the Core Bug

Implement an equivalent test in the repository:

```python
@pytest.mark.asyncio
async def test_timeout_after_commit_exposes_double_refund():
    suite = build_unsafe_refund_suite(
        mutations=[TimeoutAfterCommit(target="refund_order")]
    )

    result = await suite.run()

    failed = result.failures[0]

    assert failed.mutation.type == "timeout_after_commit"
    assert failed.mutation.target == "refund_order"
    assert "no_double_refunds" in failed.violated_invariants

    refund_effects = [
        e for e in failed.effects
        if e.type == "refund.created"
    ]

    assert len(refund_effects) == 2
    assert sum(e.data["amount"] for e in refund_effects) == 98.0

    effect_index = next(
        i for i, event in enumerate(failed.trace)
        if event.kind == "effect"
    )
    fault_index = next(
        i for i, event in enumerate(failed.trace)
        if event.kind == "fault"
    )

    assert effect_index < fault_index
```

And a corresponding fixed test:

```python
@pytest.mark.asyncio
async def test_idempotency_survives_timeout_after_commit():
    result = await build_safe_refund_suite(
        mutations=[TimeoutAfterCommit(target="refund_order")]
    ).run()

    assert result.failed_count == 0
```

---

# 52. Final Release Gate

The public v0.1 release is approved only when:

1. the deterministic refund demo finds the intended real systems failure;
2. the idempotency fix survives it;
3. replay works;
4. at least 10 stable mutation operators are genuinely tested;
5. OpenAI Agents SDK adapter has real framework integration coverage;
6. LangChain/LangGraph adapter has real framework integration coverage;
7. at least one live LLM run has been manually executed and documented, unless external API access is intentionally unavailable—in that case the README must say live validation remains pending and the release should be considered technical preview;
8. package installs from built wheel in a clean virtual environment;
9. no test/example can trigger real destructive side effects;
10. CI, lint, typing, and tests are green;
11. README makes only verifiable claims;
12. release workflow is configured safely.

---

# 53. Definition of Done

AgentProof v0.1 is **not** “done” when a repository exists.

It is done when an independent developer can:

```bash
pip install agentproof
```

write a small stateful agent test, run:

```bash
agentproof run
```

and receive evidence like:

```text
✗ timeout_after_commit:refund_order

Invariant violated: no_double_refunds
Committed effects: 2 refunds / $98.00
Expected maximum: $49.00

Reproduce:
agentproof replay .agentproof/runs/ap_xxx/repro.json
```

Then fix the agent with idempotency and get:

```text
✓ timeout_after_commit:refund_order
```

And the same fundamental mechanism must work through at least one real OpenAI Agents SDK agent and one real LangChain/LangGraph execution path.

That is the publishable first version of AgentProof.

---

# 54. Official References to Re-Verify During Implementation

Third-party APIs change. Before implementing each adapter/release path, Codex must verify current official documentation.

## OpenAI Agents SDK

- https://openai.github.io/openai-agents-python/
- https://openai.github.io/openai-agents-python/tools/
- https://openai.github.io/openai-agents-python/running_agents/

At the time this specification was prepared, the SDK documented `Agent`, `Runner`, and `FunctionTool`, with `FunctionTool.on_invoke_tool` as the runtime function-tool invocation callback.

## LangChain / LangGraph

- https://docs.langchain.com/oss/python/langchain/agents
- https://docs.langchain.com/oss/python/langchain/tools
- https://docs.langchain.com/oss/python/langgraph/quickstart
- https://docs.langchain.com/oss/python/migrate/langgraph-v1

At the time this specification was prepared, LangChain v1 documented `langchain.agents.create_agent` as the recommended agent API running on LangGraph, while LangGraph documented `ToolNode` as the prebuilt tool execution node. The older `create_react_agent` was documented as deprecated in favor of `create_agent`.

## Pytest plugin packaging

- https://docs.pytest.org/en/latest/how-to/writing_plugins.html

Pytest discovers installable plugins using the `pytest11` package entry-point group.

## PyPI Trusted Publishing

- https://docs.pypi.org/trusted-publishers/using-a-publisher/
- https://docs.pypi.org/trusted-publishers/adding-a-publisher/
- https://docs.pypi.org/trusted-publishers/security-model/

Use OIDC/Trusted Publishing and least-privilege release workflows rather than long-lived package-upload tokens.

---

# 55. Instruction to Codex When Starting

Start by reading this entire document and then create a concise `IMPLEMENTATION_PLAN.md` inside the repository mapping each phase to concrete files and tests. After that, begin Phase 1 immediately.

Do **not** ask for product-design clarification unless a decision truly blocks implementation. Prefer the defaults in this document.

At the end of every phase, report:

```text
Implemented:
Tests added:
Commands run:
Results:
Known limitations:
Next phase:
```

If you discover that a third-party API has changed, update `docs/implementation-notes.md`, link the official documentation used, adapt the implementation, and continue.

The project goal is a **truthful, technically credible, developer-useful AgentProof v0.1**, not a demo that merely looks complete.

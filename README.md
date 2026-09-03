# AgentProof

[![CI](https://github.com/rohansonawane/agentproof/actions/workflows/ci.yml/badge.svg)](https://github.com/rohansonawane/agentproof/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentproof-sim.svg)](https://pypi.org/project/agentproof-sim/)

AgentProof is a Python testing framework for AI agents that take actions through tools.

It helps you answer a practical release question:

> If a tool call times out, returns bad data, gets retried, or receives stale state, does my agent still protect the real world?

AgentProof creates an isolated simulated world, exposes tools to your agent, injects realistic faults, records the side effects that actually commit, and checks deterministic invariants over the result.

It is useful for agents that can change things:

- refunding payments;
- booking or canceling appointments;
- sending emails or support replies;
- changing CRM records;
- modifying files or repositories;
- running internal operations or DevOps workflows.

See [Real-World Use Cases](docs/use-cases.md) for concrete examples and invariants.
See [Real-Project Evidence](docs/real-project-evidence.md) for pinned public
agent-related projects that AgentProof has been run against.

AgentProof does not prove that an agent is universally safe or correct. It gives you repeatable tests for dangerous action-level failures before they reach production.

## Why This Exists

Most agent evaluations look at text: Was the answer helpful? Did the model choose the right response?

That is not enough for tool-using agents. The embarrassing failures are often stateful:

- the refund succeeded, but the agent saw a timeout and refunded again;
- the appointment was booked twice after a retry;
- the approval record changed after the agent read it;
- a malformed tool response caused the agent to act on the wrong amount;
- a duplicate event caused the same email or webhook to be sent twice.

AgentProof tests those failure modes by separating two things that production systems often blur:

- the side effect committed;
- the agent observed success.

That separation is what lets `timeout_after_commit` catch duplicate refunds, bookings, and similar bugs.

## Install

```bash
pip install agentproof-sim
```

The PyPI distribution is [`agentproof-sim`](https://pypi.org/project/agentproof-sim/) because `agentproof` is already occupied by an unrelated package. The Python import and CLI remain stable:

```python
import agentproof
```

Optional framework adapters are installed separately:

```bash
pip install "agentproof-sim[openai]"
pip install "agentproof-sim[langchain]"
```

## Five-Minute Quickstart

Save this as `refund_demo.py` and run `python refund_demo.py`.

The agent below is intentionally unsafe: if a refund commits but the response times out, it retries without an idempotency key.

```python
import asyncio
from typing import Any

from agentproof import AgentTest, World, invariant
from agentproof.core.effects import EffectDraft
from agentproof.mutations import TimeoutAfterCommit
from agentproof.tools.definition import ToolOutcome


async def refund_agent(user_input: str, tools: Any) -> str:
    del user_input
    order = await tools.call("get_order", order_id="123")
    try:
        await tools.call("refund_order", order_id="123", amount=order["total"])
    except TimeoutError:
        # Unsafe on purpose: this retry can duplicate the refund if the first
        # tool call committed before the timeout reached the agent.
        await tools.call("refund_order", order_id="123", amount=order["total"])
    return "Done"


suite = AgentTest(
    agent=refund_agent,
    adapter="native",
    mutations=[TimeoutAfterCommit(target="refund_order", severity="high")],
)


@suite.scenario(name="refund_delivered_order")
async def delivered_refund(world: World) -> None:
    world.state["orders"] = {"123": {"id": "123", "status": "delivered", "total": 49.0}}
    world.input("Refund order 123")

    async def get_order(world: World, order_id: str) -> dict[str, Any]:
        return dict(world.state["orders"][order_id])

    async def refund_order(world: World, order_id: str, amount: float) -> ToolOutcome:
        refund_id = world.next_id("refund")
        return ToolOutcome(
            value={"refund_id": refund_id},
            effects=[
                # Effects should describe work that actually committed in the
                # simulated service. Do not infer them from tool calls alone.
                EffectDraft(
                    type="refund.created",
                    operation="create",
                    resource=f"order:{order_id}",
                    data={"refund_id": refund_id, "order_id": order_id, "amount": amount},
                )
            ],
        )

    world.tools.register(
        name="get_order",
        description="Return an order.",
        input_schema={
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
        handler=get_order,
        effect="read",
    )
    world.tools.register(
        name="refund_order",
        description="Refund an order.",
        input_schema={
            "type": "object",
            "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"}},
            "required": ["order_id", "amount"],
        },
        handler=refund_order,
        effect="financial",
        idempotent=False,
    )


@invariant
def no_double_refunds(world: World) -> None:
    total = world.effects.sum(type="refund.created", where={"order_id": "123"}, field="amount")
    assert total <= 49.0, f"refunded ${total:.2f}, expected <= $49.00"


async def main() -> None:
    result = await suite.run(store_artifacts=False)
    failure = result.failures[0]
    print(failure.status)
    print(failure.violated_invariants)
    print(sum(effect.data["amount"] for effect in failure.effects))


if __name__ == "__main__":
    asyncio.run(main())
```

Expected output includes:

```text
INVARIANT_FAILURE
['no_double_refunds']
98.0
```

In plain English: the first refund happened, AgentProof hid the success response and returned a timeout, the agent retried, and the invariant caught that the customer received `$98` instead of `$49`.

## How It Works

AgentProof has five core concepts:

- `World`: isolated simulated state, virtual tools, virtual clock, event queue, effect ledger, trace, and installed faults.
- `Tool`: the action boundary exposed to an agent.
- `Effect`: an explicit committed side effect such as `refund.created` or `appointment.booked`.
- `Mutation`: a serializable fault such as `timeout_after_commit`, `missing_field`, or `duplicate_event`.
- `Invariant`: deterministic Python logic that decides whether the final state is acceptable.

The effect ledger is intentionally explicit. Tool handlers return `ToolOutcome` effects after simulated work commits. AgentProof does not guess side effects merely because a tool was called.

## What AgentProof Can Catch

AgentProof is designed for failures that happen around action boundaries:

- duplicate side effects after retries;
- partial success hidden behind a timeout;
- malformed, missing, or stale tool responses;
- rate limits and transient tool errors;
- permission denial paths;
- duplicated user requests;
- delayed or duplicated scheduled events;
- regressions where a previously idempotent action becomes unsafe.

The most important pattern is retry-after-commit:

```text
1. Agent calls refund_order.
2. The simulated refund commits.
3. AgentProof raises TimeoutError instead of returning success.
4. The agent retries.
5. A second refund commits.
6. The invariant fails.
```

## Using It Safely

AgentProof runs your test code. It is not a sandbox for untrusted code.

Use it against virtual tools, fakes, local simulators, or carefully isolated staging services. Do not point AgentProof tests at production refund, email, file deletion, deployment, payment, or account-management APIs.

Recommended safety rules:

- Replace destructive real tools with AgentProof virtual tools.
- Keep live model tests opt-in.
- Use least-privilege credentials when a live provider is required.
- Never commit API keys, tokens, customer data, or production payloads.
- Review JSON, JUnit, replay, and trace artifacts before sharing them.
- Treat redaction as a safety net, not a full data-loss-prevention system.

AgentProof redacts obvious secret fields such as `api_key`, `authorization`, `token`, `password`, and `secret` in traces and reports. It cannot know every sensitive business field in your domain. See [SECURITY.md](SECURITY.md) for the full security model.

## Stable Mutations

Stable in this technical preview:

- `tool_timeout`
- `timeout_after_commit`
- `tool_error`
- `tool_latency`
- `rate_limited`
- `malformed_response`
- `missing_field`
- `duplicate_user_request`
- `stale_state`
- `state_changed_after_read`
- `permission_denied`
- `delayed_event`
- `duplicate_event`

Experimental:

- `duplicate_tool_result`, because agent-loop semantics differ by framework.
- `reorder_tool_results`, currently rejected unless a future controlled parallel result scheduler is available.

## Framework Integrations

The core package has no OpenAI or LangChain dependency.

- Native Python callables are supported by default.
- OpenAI Agents SDK tools are wrapped as real SDK `FunctionTool` objects.
- LangChain/LangGraph tools are wrapped as real LangChain `StructuredTool` objects and tested through a compiled LangGraph `StateGraph`/`ToolNode`.

Live LLM tests are opt-in only:

```bash
# Set OPENAI_API_KEY through your shell, CI secret manager, or local secret manager first.
AGENTPROOF_RUN_LIVE_TESTS=1 pytest -m live -v
```

Do not put API keys in source files, shell history, issue comments, or README examples. Prefer temporary environment variables or a secret manager.

## Replay

Deterministic native failures write `repro.json` artifacts containing schema version, seed, mutation spec, initial snapshot, trace, and violated invariants.

```bash
agentproof replay .agentproof/runs/<run-id>/repro.json
```

Replay is for deterministic reproduction of saved failures. Live LLM behavior can vary by model, provider, and time, so live results should be treated as smoke tests rather than exact replay guarantees.

## Reports And CI

Use the CLI in CI:

```bash
agentproof run examples/refund_native/suite.py --fail-on high --json report.json --junit report.xml
```

The command exits nonzero when a failure at or above the configured severity is reproduced. That lets CI fail when AgentProof finds a high-risk behavior.

JSON and JUnit reports include scenario names, mutation names, statuses, violated invariants, failure messages, and committed effects.

For the local release-hardening gate used by this repository:

```bash
python scripts/release_hardening.py
```

External-account checks are deliberately separate:

```bash
# Set OPENAI_API_KEY outside the command before running the live gate.
AGENTPROOF_RUN_LIVE_TESTS=1 python scripts/release_hardening.py --live
python scripts/release_hardening.py --github
```

## Real-App Smoke Test

This repository includes a repeatable smoke test against a real external LangChain app:

```bash
python scripts/real_project_booking_smoke.py
```

That command clones [aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents](https://github.com/aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents), checks out a pinned commit, wraps its real `book_appointment` tool, and verifies AgentProof catches duplicate bookings caused by retry-after-timeout.

Expected summary:

```text
baseline: 1 appointment, PASS
timeout_after_commit: 2 appointments, INVARIANT_FAILURE
```

The failure is expected. It means AgentProof detected a real duplicate side effect in a real app integration.

## Production Use

AgentProof can be used in production engineering workflows as a pre-release and regression-testing tool. It should not be used as a runtime safety boundary for live autonomous agents.

Before relying on it for a real app, define virtual or staging versions of every destructive tool, add invariants for every high-risk action, run deterministic tests in CI without API keys, and keep live model checks opt-in.

See [Production Readiness](docs/production-readiness.md) for the full checklist and current limits.

## Development

```bash
python -m pip install -e ".[dev]"
ruff format .
ruff check .
mypy src/agentproof
pytest -q
```

Build and validate a wheel:

```bash
python -m build
twine check dist/*
python -m venv /tmp/agentproof-wheel-smoke
/tmp/agentproof-wheel-smoke/bin/python -m pip install dist/agentproof_sim-*.whl
/tmp/agentproof-wheel-smoke/bin/agentproof mutations
```

## Status

AgentProof is a `0.1.1` technical preview. Deterministic native execution, report generation, replay, adapter-boundary tests, clean wheel install, and CI are automated. Live model validation remains opt-in and depends on user-supplied credentials.

## License

Apache-2.0.

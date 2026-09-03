# AgentProof

AgentProof is stateful simulation and fault-injection testing for AI agents that take actions through tools.

It helps discover and regression-test action-level failures under simulated environment faults. It does not prove an agent is universally safe or correct.

```text
AgentProof
2 runs, 1 passed, 1 failed

INVARIANT_FAILURE refund_delivered_order:timeout_after_commit:refund_order
Invariant violated: no_double_refunds
refunded $98.00, expected <= $49.00
Committed effects: 2
Reproduce: agentproof replay .agentproof/runs/ap_xxx_run_001/repro.json
Seed: 42
```

## Install

```bash
pip install agentproof
```

Optional framework adapters are separate:

```bash
pip install "agentproof[openai]"
pip install "agentproof[langchain]"
```

## Five-Minute Quickstart

Save this as `refund_demo.py` and run `python refund_demo.py`.

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

## Core Concepts

World: isolated simulated state, virtual tools, virtual clock, event queue, effect ledger, trace, and installed faults.

Tool: a virtual action boundary. Tool handlers return explicit `ToolOutcome` effects; AgentProof does not infer side effects from tool calls.

Mutation: a serializable fault such as `timeout_after_commit` or `missing_field`.

Effect: a committed simulated side effect such as `refund.created`.

Invariant: deterministic Python logic over final world state, trace, and effects.

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

## Integrations

The core package has no OpenAI or LangChain dependency.

- Native Python callables are supported by default.
- OpenAI Agents SDK tools are wrapped as real SDK `FunctionTool` objects.
- LangChain/LangGraph tools are wrapped as real LangChain `StructuredTool` objects and tested through a compiled LangGraph `StateGraph`/`ToolNode`.

Live LLM tests are opt-in only:

```bash
AGENTPROOF_RUN_LIVE_TESTS=1 OPENAI_API_KEY=... pytest -m live -v
```

## Replay

Deterministic native failures write `repro.json` artifacts containing schema version, seed, mutation spec, initial snapshot, trace, and violated invariants.

```bash
agentproof replay .agentproof/runs/<run-id>/repro.json
```

## CI Usage

```bash
agentproof run examples/refund_native/suite.py --fail-on high --json report.json --junit report.xml
```

The command exits nonzero when a failure at or above the configured severity is reproduced.

For the local release-hardening gate used by this repository:

```bash
python scripts/release_hardening.py
```

External-account checks are deliberately separate:

```bash
AGENTPROOF_RUN_LIVE_TESTS=1 OPENAI_API_KEY=... python scripts/release_hardening.py --live
python scripts/release_hardening.py --github
```

## Status

AgentProof is a `0.1.0` technical preview. Deterministic native, report, replay, and local adapter-boundary tests are automated. Live model validation remains opt-in and depends on user-supplied credentials.

## License

Apache-2.0.

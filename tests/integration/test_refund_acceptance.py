from __future__ import annotations

from agentproof.mutations import TimeoutAfterCommit, ToolTimeout
from examples.refund_native.suite import build_suite


async def test_baseline_refund_creates_one_effect_and_passes() -> None:
    result = await build_suite(idempotent=False, mutations=[]).run(store_artifacts=False)

    assert result.failed_count == 0
    baseline = result.results[0]
    assert baseline.status == "PASS"
    assert len(baseline.effects) == 1
    assert baseline.effects[0].data["amount"] == 49.0


async def test_timeout_before_commit_retry_creates_one_refund() -> None:
    result = await build_suite(
        idempotent=False,
        mutations=[ToolTimeout(target="refund_order", severity="high")],
    ).run(store_artifacts=False)

    mutation_run = result.results[1]
    assert mutation_run.status == "PASS"
    assert len(mutation_run.effects) == 1
    assert sum(effect.data["amount"] for effect in mutation_run.effects) == 49.0


async def test_timeout_after_commit_exposes_double_refund() -> None:
    result = await build_suite(
        idempotent=False,
        mutations=[TimeoutAfterCommit(target="refund_order", severity="high")],
    ).run(store_artifacts=False)

    failed = result.failures[0]
    assert failed.mutation is not None
    assert failed.mutation.type == "timeout_after_commit"
    assert failed.mutation.target == "refund_order"
    assert failed.violated_invariants == ["no_double_refunds"]
    refund_effects = [effect for effect in failed.effects if effect.type == "refund.created"]
    assert len(refund_effects) == 2
    assert sum(effect.data["amount"] for effect in refund_effects) == 98.0
    kinds = [event.kind for event in failed.trace]
    assert kinds.index("effect") < kinds.index("fault")


async def test_idempotency_survives_timeout_after_commit() -> None:
    result = await build_suite(
        idempotent=True,
        mutations=[TimeoutAfterCommit(target="refund_order", severity="high")],
    ).run(store_artifacts=False)

    assert result.failed_count == 0
    mutation_run = result.results[1]
    assert len(mutation_run.effects) == 1
    assert mutation_run.effects[0].idempotency_key == "refund-order-123"


async def test_worlds_are_isolated_between_mutation_runs() -> None:
    result = await build_suite(
        idempotent=False,
        mutations=[
            TimeoutAfterCommit(target="refund_order", severity="high"),
            ToolTimeout(target="refund_order", severity="high"),
        ],
    ).run(store_artifacts=False)

    timeout_after_commit = result.results[1]
    timeout_before_commit = result.results[2]
    assert timeout_after_commit.status == "INVARIANT_FAILURE"
    assert len(timeout_after_commit.effects) == 2
    assert timeout_before_commit.status == "PASS"
    assert len(timeout_before_commit.effects) == 1

    rerun = await build_suite(idempotent=False, mutations=[]).run(store_artifacts=False)
    assert len(rerun.results[0].effects) == 1

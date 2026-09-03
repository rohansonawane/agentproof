from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from agentproof.mutations import TimeoutAfterCommit
from agentproof.replay.player import replay_artifact
from agentproof.reporting.json_report import suite_to_json, write_json_report
from agentproof.reporting.junit import write_junit_report
from examples.refund_native.suite import build_suite


async def test_replay_reproduces_failure_from_saved_seed_and_source(
    agentproof_artifacts: Path,
) -> None:
    source_path = Path("examples/refund_native/suite.py").resolve()
    result = await build_suite(
        idempotent=False,
        mutations=[TimeoutAfterCommit(target="refund_order", severity="high")],
    ).run(artifacts_dir=agentproof_artifacts, source_path=str(source_path), suite_name="suite")
    failure = result.failures[0]
    assert failure.artifact_path is not None

    replayed = await replay_artifact(failure.artifact_path)
    replay_failure = replayed.failures[0]

    assert replay_failure.seed == failure.seed
    assert replay_failure.mutation == failure.mutation
    assert replay_failure.violated_invariants == failure.violated_invariants
    assert [effect.type for effect in replay_failure.effects] == [
        effect.type for effect in failure.effects
    ]
    assert sum(effect.data["amount"] for effect in replay_failure.effects) == 98.0


async def test_json_report_contains_truthful_failure_information(tmp_path: Path) -> None:
    result = await build_suite(
        idempotent=False,
        mutations=[TimeoutAfterCommit(target="refund_order", severity="high")],
    ).run(store_artifacts=False)
    report = suite_to_json(result)

    failed = next(item for item in report["results"] if item["status"] == "INVARIANT_FAILURE")
    assert failed["violated_invariants"] == ["no_double_refunds"]
    assert len([effect for effect in failed["effects"] if effect["type"] == "refund.created"]) == 2
    assert any(
        event["kind"] == "fault" and event["name"] == "timeout_after_commit"
        for event in failed["trace"]
    )

    path = tmp_path / "agentproof.json"
    write_json_report(result, path)
    assert json.loads(path.read_text(encoding="utf-8"))["summary"]["failed"] == 1


async def test_junit_report_marks_invariant_failure(tmp_path: Path) -> None:
    result = await build_suite(
        idempotent=False,
        mutations=[TimeoutAfterCommit(target="refund_order", severity="high")],
    ).run(store_artifacts=False)
    path = tmp_path / "agentproof.xml"
    write_junit_report(result, path)

    root = ET.parse(path).getroot()
    assert root.attrib["tests"] == "2"
    assert root.attrib["failures"] == "1"
    assert root.find(".//failure") is not None

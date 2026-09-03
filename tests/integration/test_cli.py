from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentproof.cli", *args],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={"PYTHONPATH": "src:.", **os.environ},
        text=True,
        capture_output=True,
    )


def test_cli_exit_nonzero_on_high_severity_failure(tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    junit_path = tmp_path / "report.xml"

    completed = run_cli(
        "run",
        "examples/refund_native/suite.py",
        "--mutation",
        "timeout_after_commit:refund_order",
        "--fail-on",
        "high",
        "--json",
        str(json_path),
        "--junit",
        str(junit_path),
        "--no-color",
    )

    assert completed.returncode == 1
    assert "INVARIANT_FAILURE" in completed.stdout
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["failed"] == 1
    assert junit_path.exists()


def test_cli_exit_zero_when_fail_on_threshold_is_higher_than_failure(tmp_path: Path) -> None:
    completed = run_cli(
        "run",
        "examples/calendar_native/suite.py",
        "--fail-on",
        "critical",
        "--no-color",
    )

    assert completed.returncode == 0
    assert "INVARIANT_FAILURE" in completed.stdout


def test_cli_replay_returns_nonzero_for_reproduced_high_failure(tmp_path: Path) -> None:
    first = run_cli(
        "run",
        "examples/refund_native/suite.py",
        "--mutation",
        "timeout_after_commit:refund_order",
        "--fail-on",
        "high",
        "--json",
        str(tmp_path / "report.json"),
        "--no-color",
    )
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    artifact = next(item["artifact_path"] for item in report["results"] if item["artifact_path"])

    replay = run_cli("replay", artifact, "--fail-on", "high")

    assert first.returncode == 1
    assert replay.returncode == 1
    assert "no_double_refunds" in replay.stdout

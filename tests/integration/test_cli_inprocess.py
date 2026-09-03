from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agentproof.cli import main


def test_cli_mutations_doctor_and_init(tmp_path: Path) -> None:
    runner = CliRunner()

    mutations = runner.invoke(main, ["mutations"])
    assert mutations.exit_code == 0
    assert "timeout_after_commit" in mutations.output

    doctor = runner.invoke(main, ["doctor"])
    assert doctor.exit_code == 0
    assert "Python:" in doctor.output

    with runner.isolated_filesystem(temp_dir=tmp_path):
        init = runner.invoke(main, ["init"])
        assert init.exit_code == 0
        assert Path("agentproof.toml").exists()
        second = runner.invoke(main, ["init"])
        assert second.exit_code != 0
        forced = runner.invoke(main, ["init", "--force"])
        assert forced.exit_code == 0


def test_cli_run_and_replay_in_process(tmp_path: Path) -> None:
    runner = CliRunner()
    source = Path("examples/refund_native/suite.py").resolve()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        run = runner.invoke(
            main,
            [
                "run",
                str(source),
                "--mutation",
                "timeout_after_commit:refund_order",
                "--fail-on",
                "high",
                "--json",
                "report.json",
                "--junit",
                "report.xml",
                "--no-color",
            ],
        )
        assert run.exit_code == 1
        assert "INVARIANT_FAILURE" in run.output
        report = json.loads(Path("report.json").read_text(encoding="utf-8"))
        artifact = next(
            item["artifact_path"] for item in report["results"] if item["artifact_path"]
        )
        assert Path("report.xml").exists()

        replay = runner.invoke(main, ["replay", artifact, "--fail-on", "high"])
        assert replay.exit_code == 1
        assert "no_double_refunds" in replay.output

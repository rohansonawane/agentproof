from __future__ import annotations

from pathlib import Path


def test_agentproof_artifacts_fixture_comes_from_plugin(agentproof_artifacts: Path) -> None:
    assert agentproof_artifacts.exists()
    assert agentproof_artifacts.name == "runs"

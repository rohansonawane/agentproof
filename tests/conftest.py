from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def agentproof_artifacts(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    configured = request.config.getoption("--agentproof-artifacts", default=None)
    path = Path(configured) if configured else tmp_path / ".agentproof" / "runs"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


@pytest.fixture
def run_agentproof_suite(agentproof_artifacts: Path) -> Any:
    async def run(suite: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("artifacts_dir", agentproof_artifacts)
        return await suite.run(**kwargs)

    return run


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    if os.environ.get("AGENTPROOF_RUN_LIVE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="live tests require AGENTPROOF_RUN_LIVE_TESTS=1")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)

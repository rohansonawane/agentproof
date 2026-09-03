from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup("agentproof")
    group.addoption(
        "--agentproof-artifacts",
        action="store",
        default=None,
        help="Directory for AgentProof artifacts during pytest runs.",
    )


def pytest_configure(config: Any) -> None:
    config.addinivalue_line("markers", "agentproof: AgentProof framework tests")
    config.addinivalue_line("markers", "live: opt-in live model/provider tests")
    config.addinivalue_line("markers", "openai: OpenAI Agents SDK integration tests")
    config.addinivalue_line("markers", "langchain: LangChain/LangGraph integration tests")


@pytest.fixture
def agentproof_artifacts(tmp_path: Path, request: Any) -> Path:
    configured = request.config.getoption("--agentproof-artifacts")
    path = Path(configured) if configured else tmp_path / ".agentproof" / "runs"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


@pytest.fixture
def run_agentproof_suite(agentproof_artifacts: Path) -> Any:
    async def run(suite: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("artifacts_dir", agentproof_artifacts)
        return await suite.run(**kwargs)

    return run

from __future__ import annotations

import tomllib
from pathlib import Path


def test_openai_extra_includes_brotli_transport_support() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    openai_extra = pyproject["project"]["optional-dependencies"]["openai"]

    assert "openai-agents>=0.22,<1" in openai_extra
    assert "httpx2[brotli]>=2.12,<3" in openai_extra


def test_public_distribution_name_keeps_agentproof_import() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "agentproof-sim"
    assert pyproject["project"]["version"] == "0.1.1"
    assert pyproject["project"]["scripts"]["agentproof"] == "agentproof.cli:main"
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/agentproof"]
    assert (
        "agentproof-sim[test,openai,langchain]"
        in pyproject["project"]["optional-dependencies"]["dev"]
    )

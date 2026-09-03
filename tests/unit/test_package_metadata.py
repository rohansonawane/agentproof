from __future__ import annotations

import tomllib
from pathlib import Path


def test_openai_extra_includes_brotli_transport_support() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    openai_extra = pyproject["project"]["optional-dependencies"]["openai"]

    assert "openai-agents>=0.22,<1" in openai_extra
    assert "httpx2[brotli]>=2.12,<3" in openai_extra

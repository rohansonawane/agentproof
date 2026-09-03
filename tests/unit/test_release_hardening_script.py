from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def load_release_hardening() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "release_hardening.py"
    spec = importlib.util.spec_from_file_location("release_hardening", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_local_hardening_gates_do_not_consume_live_credentials(monkeypatch: Any) -> None:
    module = load_release_hardening()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("AGENTPROOF_RUN_LIVE_TESTS", "1")
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run(
        command: list[str], *, cwd: Path = module.ROOT, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        del cwd
        calls.append((command, env))
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(module, "run", fake_run)

    checks = module.run_local_quality_gates()

    assert {check.status for check in checks} == {"PASS"}
    pytest_calls = [(command, env) for command, env in calls if command[0] == "pytest"]
    assert pytest_calls
    assert all(env is not None for _, env in pytest_calls)
    assert all("AGENTPROOF_RUN_LIVE_TESTS" not in env for _, env in pytest_calls if env)
    keyless = next(
        env for command, env in pytest_calls if command == ["pytest", "-q", "-m", "not live"]
    )
    assert keyless is not None
    assert "OPENAI_API_KEY" not in keyless


def test_pytest_plugin_trace_does_not_consume_live_credentials(monkeypatch: Any) -> None:
    module = load_release_hardening()
    monkeypatch.setenv("AGENTPROOF_RUN_LIVE_TESTS", "1")
    captured_env: dict[str, str] | None = None

    def fake_run(
        command: list[str], *, cwd: Path = module.ROOT, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        del cwd
        nonlocal captured_env
        captured_env = env
        return subprocess.CompletedProcess(
            command, 0, stdout="agentproof.pytest_plugin registered\n", stderr=""
        )

    monkeypatch.setattr(module, "run", fake_run)

    check = module.run_pytest_plugin_trace()

    assert check.status == "PASS"
    assert captured_env is not None
    assert "AGENTPROOF_RUN_LIVE_TESTS" not in captured_env

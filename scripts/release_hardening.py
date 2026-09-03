from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    status: str
    detail: str
    command: str | None = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AgentProof release-hardening checks.")
    parser.add_argument(
        "--github",
        action="store_true",
        help="Attempt to trigger/watch GitHub Actions via gh. Requires a git repo and gh auth.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live tests if AGENTPROOF_RUN_LIVE_TESTS=1 and provider credentials are set.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "release-hardening-results.json",
        help="Write machine-readable check results to this path.",
    )
    args = parser.parse_args()

    checks: list[Check] = []
    checks.append(record_python())
    checks.extend(run_local_quality_gates())
    checks.extend(run_packaging_gates())
    checks.append(run_core_wheel_smoke())
    checks.append(run_optional_extras_smoke())
    checks.append(run_external_toy_project_smoke())
    checks.append(run_pytest_plugin_trace())
    checks.append(run_live_tests(args.live))
    checks.append(run_github_actions(args.github))
    write_results(checks, args.output)
    print_summary(checks, args.output)
    return 1 if any(check.status == "FAIL" for check in checks) else 0


def record_python() -> Check:
    return Check("Python version", "PASS", sys.version.split()[0], "python --version")


def run_local_quality_gates() -> list[Check]:
    local_env = without_env("AGENTPROOF_RUN_LIVE_TESTS")
    commands = [
        ("Ruff format", ["ruff", "format", "--check", "."]),
        ("Ruff lint", ["ruff", "check", "."]),
        ("Mypy", ["mypy", "src/agentproof"]),
        ("Pytest", ["pytest", "-q"], local_env),
        (
            "Keyless deterministic pytest",
            ["pytest", "-q", "-m", "not live"],
            without_env("OPENAI_API_KEY", "AGENTPROOF_RUN_LIVE_TESTS"),
        ),
        (
            "Coverage",
            [
                "pytest",
                "-q",
                "-p",
                "pytest_asyncio.plugin",
                "-p",
                "pytest_cov",
                "--cov=agentproof",
                "--cov-report=term",
            ],
            {**local_env, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        ),
    ]
    results: list[Check] = []
    for item in commands:
        name = item[0]
        command = item[1]
        env = item[2] if len(item) == 3 else None
        completed = run(command, env=env)
        detail = summarize_output(completed.stdout + completed.stderr)
        results.append(
            Check(
                name, "PASS" if completed.returncode == 0 else "FAIL", detail, command_text(command)
            )
        )
    return results


def run_packaging_gates() -> list[Check]:
    build = run([sys.executable, "-m", "build"])
    twine_paths = sorted(str(path) for path in (ROOT / "dist").glob("*"))
    twine = run(["twine", "check", *twine_paths]) if twine_paths else missing("no dist files")
    return [
        Check(
            "Build wheel/sdist",
            status_from(build),
            summarize_output(build.stdout + build.stderr),
            "python -m build",
        ),
        Check(
            "Twine check",
            status_from(twine),
            summarize_output(twine.stdout + twine.stderr),
            "twine check dist/*",
        ),
    ]


def run_core_wheel_smoke() -> Check:
    wheel = wheel_path()
    with tempfile.TemporaryDirectory(prefix="agentproof-wheel-smoke-") as temp:
        temp_path = Path(temp)
        venv = temp_path / ".venv"
        script = temp_path / "readme_quickstart.py"
        create_venv(venv)
        commands = [
            ([python_bin(venv), "-m", "pip", "install", "-q", "--upgrade", "pip"], None),
            ([python_bin(venv), "-m", "pip", "install", "-q", str(wheel)], None),
            ([script_bin(venv, "agentproof"), "mutations"], None),
        ]
        for command, env in commands:
            completed = run(command, cwd=ROOT, env=env)
            if completed.returncode != 0:
                return Check(
                    "Clean core wheel smoke",
                    "FAIL",
                    summarize_output(completed.stdout + completed.stderr),
                )
        script.write_text(readme_quickstart(), encoding="utf-8")
        completed = run([python_bin(venv), str(script)], cwd=ROOT)
        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            return Check("Clean core wheel smoke", "FAIL", summarize_output(output))
        if "INVARIANT_FAILURE" not in output or "98.0" not in output:
            return Check(
                "Clean core wheel smoke", "FAIL", f"unexpected quickstart output: {output}"
            )
        return Check("Clean core wheel smoke", "PASS", summarize_output(output))


def run_optional_extras_smoke() -> Check:
    wheel = wheel_path()
    with tempfile.TemporaryDirectory(prefix="agentproof-extras-smoke-") as temp:
        venv = Path(temp) / ".venv"
        create_venv(venv)
        install = run(
            [
                python_bin(venv),
                "-m",
                "pip",
                "install",
                "-q",
                "--upgrade",
                "pip",
            ]
        )
        if install.returncode != 0:
            return Check(
                "Optional extras smoke", "FAIL", summarize_output(install.stdout + install.stderr)
            )
        install = run(
            [python_bin(venv), "-m", "pip", "install", "-q", f"{wheel}[openai,langchain]"]
        )
        if install.returncode != 0:
            return Check(
                "Optional extras smoke", "FAIL", summarize_output(install.stdout + install.stderr)
            )
        code = """
from importlib.metadata import version
from agents import FunctionTool
from langchain.agents import create_agent
from langgraph.prebuilt import ToolNode
print("openai-agents", version("openai-agents"), FunctionTool.__name__)
print("brotli", version("brotli"))
print("langchain", version("langchain"), callable(create_agent))
print("langgraph", version("langgraph"), ToolNode.__name__)
"""
        completed = run([python_bin(venv), "-c", textwrap.dedent(code)])
        return Check(
            "Optional extras smoke",
            status_from(completed),
            summarize_output(completed.stdout + completed.stderr),
        )


def run_external_toy_project_smoke() -> Check:
    wheel = wheel_path()
    with tempfile.TemporaryDirectory(prefix="agentproof-external-project-") as temp:
        project = Path(temp)
        venv = project / ".venv"
        create_venv(venv)
        install = run([python_bin(venv), "-m", "pip", "install", "-q", "--upgrade", "pip"])
        if install.returncode != 0:
            return Check(
                "External toy project smoke",
                "FAIL",
                summarize_output(install.stdout + install.stderr),
            )
        install = run([python_bin(venv), "-m", "pip", "install", "-q", str(wheel)])
        if install.returncode != 0:
            return Check(
                "External toy project smoke",
                "FAIL",
                summarize_output(install.stdout + install.stderr),
            )
        suite = project / "billing_agent_suite.py"
        suite.write_text(external_project_suite(), encoding="utf-8")
        completed = run(
            [
                script_bin(venv, "agentproof"),
                "run",
                str(suite),
                "--mutation",
                "timeout_after_commit:charge_card",
                "--fail-on",
                "high",
                "--json",
                str(project / "report.json"),
                "--junit",
                str(project / "report.xml"),
                "--no-color",
            ],
            cwd=project,
        )
        if completed.returncode != 1:
            detail = (
                f"expected exit 1, got {completed.returncode}: "
                f"{summarize_output(completed.stdout + completed.stderr)}"
            )
            return Check(
                "External toy project smoke",
                "FAIL",
                detail,
            )
        report = json.loads((project / "report.json").read_text(encoding="utf-8"))
        failure = next(item for item in report["results"] if item["status"] == "INVARIANT_FAILURE")
        effects = [effect for effect in failure["effects"] if effect["type"] == "payment.charged"]
        if len(effects) != 2:
            return Check(
                "External toy project smoke",
                "FAIL",
                f"expected 2 payment effects, got {len(effects)}",
            )
        ET.parse(project / "report.xml")
        return Check(
            "External toy project smoke", "PASS", "independent temp project found duplicate charge"
        )


def run_pytest_plugin_trace() -> Check:
    completed = run(
        ["pytest", "--trace-config", "-q"], env=without_env("AGENTPROOF_RUN_LIVE_TESTS")
    )
    output = completed.stdout + completed.stderr
    if completed.returncode == 0 and "agentproof.pytest_plugin" in output:
        return Check("Pytest plugin entry point", "PASS", "agentproof.pytest_plugin registered")
    return Check("Pytest plugin entry point", "FAIL", summarize_output(output))


def run_live_tests(enabled: bool) -> Check:
    if not enabled:
        return Check("Live tests", "SKIP", "pass --live and set credentials to run")
    if os.environ.get("AGENTPROOF_RUN_LIVE_TESTS") != "1":
        return Check("Live tests", "SKIP", "AGENTPROOF_RUN_LIVE_TESTS=1 is required")
    if not os.environ.get("OPENAI_API_KEY"):
        return Check("Live tests", "SKIP", "OPENAI_API_KEY is required")
    completed = run(["pytest", "-q", "-m", "live"])
    return Check(
        "Live tests", status_from(completed), summarize_output(completed.stdout + completed.stderr)
    )


def run_github_actions(enabled: bool) -> Check:
    if not enabled:
        return Check("GitHub Actions CI matrix", "SKIP", "pass --github to trigger with gh")
    if not (ROOT / ".git").exists():
        return Check("GitHub Actions CI matrix", "SKIP", "workspace is not a git repository")
    if shutil.which("gh") is None:
        return Check("GitHub Actions CI matrix", "SKIP", "gh CLI is not installed")
    auth = run(["gh", "auth", "status"])
    if auth.returncode != 0:
        return Check("GitHub Actions CI matrix", "SKIP", "gh is not authenticated")
    branch = run(["git", "branch", "--show-current"])
    ref = branch.stdout.strip() or "HEAD"
    trigger = run(["gh", "workflow", "run", "ci.yml", "--ref", ref])
    if trigger.returncode != 0:
        return Check(
            "GitHub Actions CI matrix", "FAIL", summarize_output(trigger.stdout + trigger.stderr)
        )
    return Check("GitHub Actions CI matrix", "PASS", f"triggered ci.yml on {ref}")


def write_results(checks: list[Check], path: Path) -> None:
    payload = {
        "schema_version": 1,
        "results": [check.__dict__ for check in checks],
        "summary": {
            "passed": len([check for check in checks if check.status == "PASS"]),
            "failed": len([check for check in checks if check.status == "FAIL"]),
            "skipped": len([check for check in checks if check.status == "SKIP"]),
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def print_summary(checks: list[Check], path: Path) -> None:
    for check in checks:
        command = f" ({check.command})" if check.command else ""
        print(f"{check.status:4} {check.name}{command}: {check.detail}")
    print(f"wrote {path}")


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def missing(message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=message)


def status_from(completed: subprocess.CompletedProcess[str]) -> str:
    return "PASS" if completed.returncode == 0 else "FAIL"


def summarize_output(output: str, *, max_lines: int = 4) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "ok"
    interesting = lines[-max_lines:]
    return " | ".join(interesting)


def command_text(command: list[str]) -> str:
    return " ".join(command)


def without_env(*keys: str) -> dict[str, str]:
    env = dict(os.environ)
    for key in keys:
        env.pop(key, None)
    return env


def create_venv(path: Path) -> None:
    completed = run([sys.executable, "-m", "venv", str(path)])
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)


def python_bin(venv: Path) -> str:
    return str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def script_bin(venv: Path, name: str) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    return str(venv / ("Scripts" if os.name == "nt" else "bin") / f"{name}{suffix}")


def wheel_path() -> Path:
    wheels = sorted((ROOT / "dist").glob("agentproof-*.whl"))
    if not wheels:
        raise FileNotFoundError("no built AgentProof wheel under dist/")
    return wheels[-1]


def readme_quickstart() -> str:
    match = re.search(
        r"```python\n(.*?)\n```", (ROOT / "README.md").read_text(encoding="utf-8"), re.DOTALL
    )
    if match is None:
        raise ValueError("README has no Python quickstart block")
    return match.group(1)


def external_project_suite() -> str:
    return textwrap.dedent(
        """
        from __future__ import annotations

        from typing import Any

        from agentproof import AgentTest, World, invariant
        from agentproof.core.effects import EffectDraft
        from agentproof.mutations import TimeoutAfterCommit
        from agentproof.tools.definition import ToolOutcome


        async def billing_agent(user_input: str, tools: Any) -> str:
            del user_input
            try:
                await tools.call("charge_card", customer_id="cus_123", amount=25.0)
            except TimeoutError:
                await tools.call("charge_card", customer_id="cus_123", amount=25.0)
            return "done"


        suite = AgentTest(
            agent=billing_agent,
            adapter="native",
            mutations=[TimeoutAfterCommit(target="charge_card", severity="high")],
        )


        @suite.scenario(name="charge_customer_once")
        async def charge_customer_once(world: World) -> None:
            world.input("Charge customer cus_123 once.")

            async def charge_card(world: World, customer_id: str, amount: float) -> ToolOutcome:
                charge_id = world.next_id("charge")
                return ToolOutcome(
                    value={"charge_id": charge_id},
                    effects=[
                        EffectDraft(
                            type="payment.charged",
                            operation="create",
                            resource=f"customer:{customer_id}",
                            data={
                                "charge_id": charge_id,
                                "customer_id": customer_id,
                                "amount": amount,
                            },
                        )
                    ],
                )

            world.tools.register(
                name="charge_card",
                description="Create a simulated card charge.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "amount": {"type": "number"},
                    },
                    "required": ["customer_id", "amount"],
                },
                handler=charge_card,
                effect="financial",
                idempotent=False,
            )


        @invariant
        def no_duplicate_charge(world: World) -> None:
            total = world.effects.sum(
                type="payment.charged",
                where={"customer_id": "cus_123"},
                field="amount",
            )
            assert total <= 25.0, f"charged ${total:.2f}, expected <= $25.00"
        """
    )


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_URL = (
    "https://github.com/aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents.git"
)
DEFAULT_REF = "7cc5937038ceb9d90a1212257d31233d265ef519"
DEPENDENCIES = ["streamlit", "langchain-core", "pyyaml", "python-dotenv"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AgentProof against a real external booking-agent project."
    )
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--agentproof-path", type=Path, default=ROOT)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "real-project-validation-results.json",
        help="Write summarized validation results to this path.",
    )
    args = parser.parse_args()

    temp_root = Path(tempfile.mkdtemp(prefix="agentproof-real-project-"))
    try:
        result = run_probe(args.repo_url, args.ref, args.agentproof_path, temp_root)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        print(f"wrote {args.output}")
        return 0 if result["passed"] else 1
    finally:
        if args.keep_temp:
            print(f"kept temp directory: {temp_root}")
        else:
            shutil.rmtree(temp_root)


def run_probe(repo_url: str, ref: str, agentproof_path: Path, temp_root: Path) -> dict[str, object]:
    repo_dir = temp_root / "booking-project"
    venv = temp_root / ".venv"
    harness = temp_root / "agentproof_booking_probe.py"
    raw_result_path = temp_root / "raw-result.json"

    checked(run(["git", "clone", repo_url, str(repo_dir)]), "clone external repository")
    checked(run(["git", "checkout", ref], cwd=repo_dir), "checkout pinned external commit")
    actual_ref = checked(run(["git", "rev-parse", "HEAD"], cwd=repo_dir), "read external commit")
    harness.write_text(harness_source(), encoding="utf-8")

    checked(run([sys.executable, "-m", "venv", str(venv)]), "create virtual environment")
    python = python_bin(venv)
    checked(run([python, "-m", "pip", "install", "-q", "--upgrade", "pip"]), "upgrade pip")
    checked(
        run([python, "-m", "pip", "install", "-q", str(agentproof_path), *DEPENDENCIES]),
        "install AgentProof and minimal external dependencies",
    )

    env = dict(os.environ)
    env["GROQ_API_KEY"] = "agentproof-dummy-key-for-import-only"
    env["PYTHONPATH"] = str(repo_dir)
    completed = run([python, str(harness), str(repo_dir), str(raw_result_path)], env=env)
    if completed.returncode != 0:
        return {
            "passed": False,
            "repo_url": repo_url,
            "requested_ref": ref,
            "actual_ref": actual_ref.stdout.strip(),
            "error": summarize_output(completed.stdout + completed.stderr, max_lines=12),
        }

    raw = json.loads(raw_result_path.read_text(encoding="utf-8"))
    raw.update(
        {
            "passed": True,
            "repo_url": repo_url,
            "requested_ref": ref,
            "actual_ref": actual_ref.stdout.strip(),
        }
    )
    return raw


def harness_source() -> str:
    return textwrap.dedent(
        """
        from __future__ import annotations

        import json
        import os
        import sys
        from pathlib import Path
        from typing import Any

        repo_dir = Path(sys.argv[1])
        result_path = Path(sys.argv[2])
        os.chdir(repo_dir)
        sys.path.insert(0, str(repo_dir))

        import streamlit as st
        from agentproof import AgentTest, World, invariant
        from agentproof.core.effects import EffectDraft
        from agentproof.mutations import TimeoutAfterCommit
        from agentproof.tools.definition import ToolOutcome
        from tools import book_appointment

        PAYLOAD = {
            "person_name": "Rohan",
            "appointment_type": "demo",
            "appointment_year": 2026,
            "appointment_month": 9,
            "appointment_day": 10,
            "appointment_hour": 10,
            "appointment_minute": 30,
        }


        async def retrying_booking_agent(user_input: str, tools: Any) -> str:
            del user_input
            try:
                await tools.call("book_appointment", **PAYLOAD)
            except TimeoutError:
                await tools.call("book_appointment", **PAYLOAD)
            return "done"


        suite = AgentTest(
            agent=retrying_booking_agent,
            adapter="native",
            mutations=[TimeoutAfterCommit(target="book_appointment", severity="high")],
            name="external_booking_project",
        )


        @suite.scenario(name="book_one_appointment")
        async def book_one_appointment(world: World) -> None:
            st.session_state.appointments = []
            world.input("Book Rohan a demo appointment on Sept 10 2026 at 10:30.")

            async def wrapped_book_appointment(world: World, **kwargs: Any) -> ToolOutcome:
                before = len(st.session_state.appointments)
                result = book_appointment.invoke(kwargs)
                after = len(st.session_state.appointments)
                effects = []
                new_items = list(st.session_state.appointments[before:after])
                for index, appointment in enumerate(new_items, start=before + 1):
                    effects.append(
                        EffectDraft(
                            type="appointment.booked",
                            operation="create",
                            resource=f"appointment:{appointment['time'].isoformat()}",
                            data={
                                "appointment_index": index,
                                "name": appointment["name"],
                                "type": appointment["type"],
                                "time": appointment["time"].isoformat(),
                            },
                        )
                    )
                return ToolOutcome(value=result, effects=effects)

            world.tools.register(
                name="book_appointment",
                description="Book an appointment using the external project tool.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "person_name": {"type": "string"},
                        "appointment_type": {"type": "string"},
                        "appointment_year": {"type": "integer"},
                        "appointment_month": {"type": "integer"},
                        "appointment_day": {"type": "integer"},
                        "appointment_hour": {"type": "integer"},
                        "appointment_minute": {"type": "integer"},
                    },
                    "required": list(PAYLOAD),
                },
                handler=wrapped_book_appointment,
                effect="write",
                idempotent=False,
            )


        @invariant(severity="high")
        def no_duplicate_appointments(world: World) -> None:
            effects = world.effects.filter(type="appointment.booked")
            actual = list(st.session_state.appointments)
            assert len(effects) == len(actual), (
                f"ledger has {len(effects)} effects but external state has "
                f"{len(actual)} appointments"
            )
            assert len(effects) <= 1, f"booked {len(effects)} appointments, expected <= 1"


        suite.add_invariant(no_duplicate_appointments)
        result = suite.run_sync(store_artifacts=False)
        runs = [
            {
                "name": run.name,
                "status": run.status,
                "effect_count": len(run.effects),
                "violated_invariants": run.violated_invariants,
                "failure": run.error_message,
                "effects": [effect.model_dump(mode="json") for effect in run.effects],
            }
            for run in result.results
        ]
        payload = {
            "external_project": (
                "aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents"
            ),
            "summary": {
                "total": result.total_count,
                "passed": result.passed_count,
                "failed": result.failed_count,
            },
            "runs": runs,
        }
        result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        baseline = next(run for run in result.results if run.mutation is None)
        mutated = next(run for run in result.results if run.mutation is not None)
        assert baseline.status == "PASS"
        assert len(baseline.effects) == 1
        assert mutated.status == "INVARIANT_FAILURE"
        assert len(mutated.effects) == 2
        assert mutated.violated_invariants == ["no_duplicate_appointments"]
        """
    )


def checked(
    completed: subprocess.CompletedProcess[str], label: str
) -> subprocess.CompletedProcess[str]:
    if completed.returncode != 0:
        output = summarize_output(completed.stdout + completed.stderr, max_lines=8)
        raise RuntimeError(f"{label} failed: {output}")
    return completed


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
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


def summarize_output(output: str, *, max_lines: int = 4) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return " | ".join(lines[-max_lines:]) if lines else "ok"


def python_bin(venv: Path) -> str:
    return str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


if __name__ == "__main__":
    raise SystemExit(main())

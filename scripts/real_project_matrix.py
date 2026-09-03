from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEPENDENCIES = [
    "streamlit",
    "langchain-core",
    "langchain-groq",
    "pyyaml",
    "python-dotenv",
    "pytz",
    "schedule",
]


@dataclass(frozen=True)
class IncludedProject:
    key: str
    name: str
    repo_url: str
    ref: str
    framework_boundary: str
    side_effect: str
    expected_signal: str


INCLUDED_PROJECTS = [
    IncludedProject(
        key="langchain_booking_appointment_create",
        name="aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents",
        repo_url=(
            "https://github.com/aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents.git"
        ),
        ref="7cc5937038ceb9d90a1212257d31233d265ef519",
        framework_boundary="LangChain StructuredTool.invoke",
        side_effect="streamlit.session_state.appointments append",
        expected_signal="unsafe retry creates two real appointments and fails invariant",
    ),
    IncludedProject(
        key="langchain_medora_appointment_reschedule",
        name="extremecoder-rgb/medoraAI",
        repo_url="https://github.com/extremecoder-rgb/medoraAI.git",
        ref="26838fc355628e0383ae59dd8acf1b02ed2920e1",
        framework_boundary="LangChain StructuredTool.invoke",
        side_effect="streamlit.session_state.appointments in-place update",
        expected_signal=(
            "retry does not create a second ledger effect when no second state change occurs"
        ),
    ),
    IncludedProject(
        key="custom_tool_file_append",
        name="Notnaton/oiv2",
        repo_url="https://github.com/Notnaton/oiv2.git",
        ref="489923b679ab63d4edf2bd879e75486592a0c1fc",
        framework_boundary="project-local function_tool wrapper",
        side_effect="filesystem append inside isolated temporary project directory",
        expected_signal="unsafe retry appends twice and fails invariant",
    ),
]

REJECTED_PROJECTS = [
    {
        "name": "kapa-ai/langchain-agent-example",
        "repo_url": "https://github.com/kapa-ai/langchain-agent-example",
        "ref": "c441a42c5956710d64e64a40bbea353a12db9afb",
        "reason": "tool files are explicitly mock/read-only examples, not real state mutations",
    },
    {
        "name": "Hegazy360/langchain-multi-agent",
        "repo_url": "https://github.com/Hegazy360/langchain-multi-agent",
        "ref": "0950344d913f30846321a31d0cc08b1f4c2bcfc1",
        "reason": (
            "imports live OpenAI/Tavily dependencies and the mutating-looking tool is a placeholder"
        ),
    },
    {
        "name": "hungson175/mini-claw-code",
        "repo_url": "https://github.com/hungson175/mini-claw-code",
        "ref": "2c22914b4c23242ff1c9d28d2bc6e4e0e3b5411a",
        "reason": "module starts an interactive live-LLM loop at import time",
    },
    {
        "name": "AdityaUnal/RentalShop",
        "repo_url": "https://github.com/AdityaUnal/RentalShop",
        "ref": "add45b60fbe71ae170d720cf960348a889403e64",
        "reason": (
            "real SQLite writes exist, but module import initializes HuggingFace/retriever stack"
        ),
    },
    {
        "name": "cornflowerblu/strands-agent-shopper",
        "repo_url": "https://github.com/cornflowerblu/strands-agent-shopper",
        "ref": "9dfee90716811bf9cc1dcfc0e31480fe82d1b3ef",
        "reason": "real cart operations require authenticated HEB account state",
    },
    {
        "name": "sujay3srivastava/AI-Agent-Hackathon",
        "repo_url": "https://github.com/sujay3srivastava/AI-Agent-Hackathon",
        "ref": "13892eeda6e8afab083f58696301e8a00ab72a52",
        "reason": (
            "appointment tool is real, but the page reads Streamlit secrets and calls "
            "OpenAI at import"
        ),
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AgentProof against pinned public agent-related projects."
    )
    parser.add_argument(
        "--project",
        choices=[project.key for project in INCLUDED_PROJECTS],
        action="append",
        help="Run only this included project. May be repeated.",
    )
    parser.add_argument("--agentproof-path", type=Path, default=ROOT)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "real-project-matrix-results.json",
        help="Write summarized validation results to this path.",
    )
    args = parser.parse_args()

    selected = [
        project
        for project in INCLUDED_PROJECTS
        if args.project is None or project.key in set(args.project)
    ]
    temp_root = Path(tempfile.mkdtemp(prefix="agentproof-real-project-matrix-"))
    try:
        result = run_matrix(
            selected_projects=selected,
            agentproof_path=args.agentproof_path.resolve(),
            temp_root=temp_root,
        )
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        print(f"wrote {args.output}")
        return 0 if result["passed"] else 1
    finally:
        if args.keep_temp:
            print(f"kept temp directory: {temp_root}")
        else:
            shutil.rmtree(temp_root)


def run_matrix(
    *,
    selected_projects: list[IncludedProject],
    agentproof_path: Path,
    temp_root: Path,
) -> dict[str, Any]:
    repos_root = temp_root / "repos"
    repos_root.mkdir()
    venv = temp_root / ".venv"
    raw_results_dir = temp_root / "raw-results"
    raw_results_dir.mkdir()
    harness_dir = temp_root / "harnesses"
    harness_dir.mkdir()

    checked(run([sys.executable, "-m", "venv", str(venv)]), "create virtual environment")
    python = python_bin(venv)
    checked(run([python, "-m", "pip", "install", "-q", "--upgrade", "pip"]), "upgrade pip")
    checked(
        run([python, "-m", "pip", "install", "-q", str(agentproof_path), *DEPENDENCIES]),
        "install AgentProof and external project dependencies",
    )
    version = checked(
        run([python, "-c", "import agentproof; print(agentproof.__version__)"]),
        "read installed AgentProof version",
    ).stdout.strip()

    results: list[dict[str, Any]] = []
    for project in selected_projects:
        project_result = run_project(
            project=project,
            python=python,
            repos_root=repos_root,
            harness_dir=harness_dir,
            raw_results_dir=raw_results_dir,
        )
        results.append(project_result)

    summary = summarize(results)
    return {
        "passed": all(item["passed"] for item in results),
        "generated_at": datetime.now(UTC).isoformat(),
        "agentproof_version": version,
        "agentproof_source": "local checkout installed into a clean temporary virtual environment",
        "summary": summary,
        "included_projects": results,
        "rejected_projects": REJECTED_PROJECTS,
    }


def run_project(
    *,
    project: IncludedProject,
    python: str,
    repos_root: Path,
    harness_dir: Path,
    raw_results_dir: Path,
) -> dict[str, Any]:
    repo_dir = repos_root / project.key
    raw_result_path = raw_results_dir / f"{project.key}.json"
    harness_path = harness_dir / f"{project.key}.py"

    checked(
        run(["git", "clone", "--quiet", project.repo_url, str(repo_dir)]),
        f"clone {project.name}",
    )
    checked(
        run(["git", "checkout", "--quiet", project.ref], cwd=repo_dir),
        f"checkout {project.name}",
    )
    actual_ref = checked(
        run(["git", "rev-parse", "HEAD"], cwd=repo_dir),
        f"read {project.name} ref",
    )

    harness_path.write_text(harness_source(project.key), encoding="utf-8")
    env = dict(os.environ)
    env.update(
        {
            "GROQ_API_KEY": "agentproof-dummy-key-for-import-only",
            "OPENAI_API_KEY": "",
            "PYTHONPATH": str(repo_dir),
        }
    )

    completed = run([python, str(harness_path), str(repo_dir), str(raw_result_path)], env=env)
    base = {
        "key": project.key,
        "name": project.name,
        "repo_url": project.repo_url.removesuffix(".git"),
        "requested_ref": project.ref,
        "actual_ref": actual_ref.stdout.strip(),
        "framework_boundary": project.framework_boundary,
        "side_effect": project.side_effect,
        "expected_signal": project.expected_signal,
    }
    if completed.returncode != 0:
        return {
            **base,
            "passed": False,
            "error": summarize_output(completed.stdout + completed.stderr, max_lines=18),
        }

    raw = json.loads(raw_result_path.read_text(encoding="utf-8"))
    return {**base, "passed": True, **raw}


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    run_count = 0
    invariant_failures = 0
    expected_failures_detected = 0
    duplicate_side_effects_detected = 0
    total_effects = 0
    for project in results:
        for scenario_run in project.get("runs", []):
            run_count += 1
            if scenario_run.get("status") == "INVARIANT_FAILURE":
                invariant_failures += 1
            if scenario_run.get("expected_failure_detected"):
                expected_failures_detected += 1
            if scenario_run.get("duplicate_side_effect_detected"):
                duplicate_side_effects_detected += 1
            total_effects += int(scenario_run.get("effect_count", 0))
    return {
        "projects_tested": len(results),
        "agentproof_runs": run_count,
        "invariant_failures": invariant_failures,
        "expected_failures_detected": expected_failures_detected,
        "duplicate_side_effects_detected": duplicate_side_effects_detected,
        "effects_recorded": total_effects,
    }


def harness_source(project_key: str) -> str:
    if project_key == "langchain_booking_appointment_create":
        return booking_harness_source()
    if project_key == "langchain_medora_appointment_reschedule":
        return medora_harness_source()
    if project_key == "custom_tool_file_append":
        return oiv2_harness_source()
    raise ValueError(f"unknown harness project: {project_key}")


def booking_harness_source() -> str:
    return textwrap.dedent(
        """
        from __future__ import annotations

        import json
        import os
        import sys
        from pathlib import Path
        from typing import Any

        repo_dir = Path(sys.argv[1]).resolve()
        result_path = Path(sys.argv[2])
        os.chdir(repo_dir)
        sys.path.insert(0, str(repo_dir))

        import streamlit as st
        from agentproof import AgentTest, World, invariant
        from agentproof.core.effects import EffectDraft
        from agentproof.mutations import TimeoutAfterCommit
        from agentproof.tools.definition import ToolOutcome
        from tools import book_appointment


        def serialize_runs(runs: Any) -> list[dict[str, Any]]:
            serialized = []
            for run in runs:
                effect_count = len(run.effects)
                serialized.append(
                    {
                        "name": run.name,
                        "status": run.status,
                        "mutation": run.mutation.type if run.mutation else None,
                        "effect_count": effect_count,
                        "external_side_effect_count": effect_count,
                        "expected_failure_detected": run.status == "INVARIANT_FAILURE",
                        "duplicate_side_effect_detected": effect_count == 2,
                        "violated_invariants": run.violated_invariants,
                        "failure": run.error_message,
                        "effects": [effect.model_dump(mode="json") for effect in run.effects],
                    }
                )
            return serialized


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
        runs = serialize_runs(result.results)
        payload = {
            "scenario": "Retry a real LangChain appointment-creation tool after commit timeout.",
            "assertions": [
                "baseline_status_pass",
                "baseline_effects_equal_real_appointments",
                "mutated_status_invariant_failure",
                "mutated_effects_equal_real_appointments",
                "mutated_real_appointments_count_is_2",
            ],
            "runs": runs,
        }
        result_path.write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")

        baseline = next(run for run in result.results if run.mutation is None)
        mutated = next(run for run in result.results if run.mutation is not None)
        assert baseline.status == "PASS"
        assert len(baseline.effects) == 1
        assert mutated.status == "INVARIANT_FAILURE"
        assert len(mutated.effects) == 2
        assert mutated.violated_invariants == ["no_duplicate_appointments"]


        def serialize_runs(runs: Any) -> list[dict[str, Any]]:
            serialized = []
            for run in runs:
                effect_count = len(run.effects)
                serialized.append(
                    {
                        "name": run.name,
                        "status": run.status,
                        "mutation": run.mutation.type if run.mutation else None,
                        "effect_count": effect_count,
                        "external_side_effect_count": effect_count,
                        "expected_failure_detected": run.status == "INVARIANT_FAILURE",
                        "duplicate_side_effect_detected": effect_count == 2,
                        "violated_invariants": run.violated_invariants,
                        "failure": run.error_message,
                        "effects": [effect.model_dump(mode="json") for effect in run.effects],
                    }
                )
            return serialized
        """
    )


def medora_harness_source() -> str:
    return textwrap.dedent(
        """
        from __future__ import annotations

        import datetime
        import json
        import os
        import sys
        from pathlib import Path
        from typing import Any

        repo_dir = Path(sys.argv[1]).resolve()
        result_path = Path(sys.argv[2])
        os.chdir(repo_dir)
        sys.path.insert(0, str(repo_dir))

        import streamlit as st
        from agentproof import AgentTest, World, invariant
        from agentproof.core.effects import EffectDraft
        from agentproof.mutations import TimeoutAfterCommit
        from agentproof.tools.definition import ToolOutcome
        from tools import reschedule_appointment


        def serialize_runs(runs: Any) -> list[dict[str, Any]]:
            serialized = []
            for run in runs:
                effect_count = len(run.effects)
                serialized.append(
                    {
                        "name": run.name,
                        "status": run.status,
                        "mutation": run.mutation.type if run.mutation else None,
                        "effect_count": effect_count,
                        "external_side_effect_count": effect_count,
                        "expected_failure_detected": False,
                        "duplicate_side_effect_detected": False,
                        "violated_invariants": run.violated_invariants,
                        "failure": run.error_message,
                        "effects": [effect.model_dump(mode="json") for effect in run.effects],
                    }
                )
            return serialized


        OLD_TIME = datetime.datetime(2026, 9, 9, 10, 0)
        NEW_TIME = datetime.datetime(2026, 9, 11, 10, 0)
        PAYLOAD = {
            "old_year": OLD_TIME.year,
            "old_month": OLD_TIME.month,
            "old_day": OLD_TIME.day,
            "old_hour": OLD_TIME.hour,
            "old_minute": OLD_TIME.minute,
            "new_year": NEW_TIME.year,
            "new_month": NEW_TIME.month,
            "new_day": NEW_TIME.day,
            "new_hour": NEW_TIME.hour,
            "new_minute": NEW_TIME.minute,
            "patient_name": "Rohan",
        }


        async def retrying_reschedule_agent(user_input: str, tools: Any) -> str:
            del user_input
            try:
                await tools.call("reschedule_appointment", **PAYLOAD)
            except TimeoutError:
                await tools.call("reschedule_appointment", **PAYLOAD)
            return "done"


        suite = AgentTest(
            agent=retrying_reschedule_agent,
            adapter="native",
            mutations=[TimeoutAfterCommit(target="reschedule_appointment", severity="high")],
            name="external_medora_project",
        )


        @suite.scenario(name="reschedule_one_appointment")
        async def reschedule_one_appointment(world: World) -> None:
            st.session_state.appointments = [
                {
                    "name": "Rohan",
                    "type": "consultation",
                    "time": OLD_TIME,
                    "doctor_name": "Dr. Smith",
                    "status": "booked",
                }
            ]
            world.input("Move Rohan's appointment from Sept 9 to Sept 11.")

            async def wrapped_reschedule_appointment(world: World, **kwargs: Any) -> ToolOutcome:
                before = snapshot_appointments()
                result = reschedule_appointment.invoke(kwargs)
                after = snapshot_appointments()
                effects = []
                for before_item, after_item in zip(before, after, strict=True):
                    if before_item != after_item:
                        effects.append(
                            EffectDraft(
                                type="appointment.rescheduled",
                                operation="update",
                                resource=f"appointment:{before_item['time']}",
                                data={
                                    "name": after_item["name"],
                                    "doctor_name": after_item["doctor_name"],
                                    "old_time": before_item["time"],
                                    "new_time": after_item["time"],
                                    "status": after_item["status"],
                                },
                            )
                        )
                return ToolOutcome(value=result, effects=effects)

            world.tools.register(
                name="reschedule_appointment",
                description="Reschedule an appointment using the external project tool.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "old_year": {"type": "integer"},
                        "old_month": {"type": "integer"},
                        "old_day": {"type": "integer"},
                        "old_hour": {"type": "integer"},
                        "old_minute": {"type": "integer"},
                        "new_year": {"type": "integer"},
                        "new_month": {"type": "integer"},
                        "new_day": {"type": "integer"},
                        "new_hour": {"type": "integer"},
                        "new_minute": {"type": "integer"},
                        "patient_name": {"type": "string"},
                    },
                    "required": list(PAYLOAD),
                },
                handler=wrapped_reschedule_appointment,
                effect="write",
                idempotent=True,
            )


        @invariant(severity="high")
        def ledger_matches_actual_reschedules(world: World) -> None:
            effects = world.effects.filter(type="appointment.rescheduled")
            actual = snapshot_appointments()
            changed = [item for item in actual if item["time"] == NEW_TIME.isoformat()]
            assert len(effects) == len(changed), (
                f"ledger has {len(effects)} effects but external state has "
                f"{len(changed)} rescheduled appointments"
            )
            assert len(effects) <= 1, f"rescheduled {len(effects)} times, expected <= 1"


        def snapshot_appointments() -> list[dict[str, Any]]:
            return [
                {
                    "name": item["name"],
                    "type": item["type"],
                    "time": item["time"].isoformat(),
                    "doctor_name": item.get("doctor_name"),
                    "status": item.get("status"),
                }
                for item in st.session_state.appointments
            ]


        suite.add_invariant(ledger_matches_actual_reschedules)
        result = suite.run_sync(store_artifacts=False)
        runs = serialize_runs(result.results)
        payload = {
            "scenario": "Retry a real LangChain appointment-reschedule tool after commit timeout.",
            "assertions": [
                "baseline_status_pass",
                "baseline_effects_equal_real_reschedules",
                "mutated_status_pass",
                "mutated_effects_equal_real_reschedules",
                "mutated_real_reschedules_count_is_1",
            ],
            "runs": runs,
        }
        result_path.write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")

        baseline = next(run for run in result.results if run.mutation is None)
        mutated = next(run for run in result.results if run.mutation is not None)
        assert baseline.status == "PASS"
        assert len(baseline.effects) == 1
        assert mutated.status == "PASS"
        assert len(mutated.effects) == 1


        def serialize_runs(runs: Any) -> list[dict[str, Any]]:
            serialized = []
            for run in runs:
                effect_count = len(run.effects)
                serialized.append(
                    {
                        "name": run.name,
                        "status": run.status,
                        "mutation": run.mutation.type if run.mutation else None,
                        "effect_count": effect_count,
                        "external_side_effect_count": effect_count,
                        "expected_failure_detected": False,
                        "duplicate_side_effect_detected": False,
                        "violated_invariants": run.violated_invariants,
                        "failure": run.error_message,
                        "effects": [effect.model_dump(mode="json") for effect in run.effects],
                    }
                )
            return serialized
        """
    )


def oiv2_harness_source() -> str:
    return textwrap.dedent(
        """
        from __future__ import annotations

        import json
        import os
        import sys
        from pathlib import Path
        from typing import Any

        repo_dir = Path(sys.argv[1]).resolve()
        result_path = Path(sys.argv[2])
        os.chdir(repo_dir)
        sys.path.insert(0, str(repo_dir))

        from agentproof import AgentTest, World, invariant
        from agentproof.core.effects import EffectDraft
        from agentproof.mutations import TimeoutAfterCommit
        from agentproof.tools.definition import ToolOutcome
        from oiv2.tools.files import write


        def serialize_runs(runs: Any) -> list[dict[str, Any]]:
            serialized = []
            for run in runs:
                effect_count = len(run.effects)
                serialized.append(
                    {
                        "name": run.name,
                        "status": run.status,
                        "mutation": run.mutation.type if run.mutation else None,
                        "effect_count": effect_count,
                        "external_side_effect_count": effect_count,
                        "expected_failure_detected": run.status == "INVARIANT_FAILURE",
                        "duplicate_side_effect_detected": effect_count == 2,
                        "violated_invariants": run.violated_invariants,
                        "failure": run.error_message,
                        "effects": [effect.model_dump(mode="json") for effect in run.effects],
                    }
                )
            return serialized


        TARGET_FILE = repo_dir / ".agentproof-sandbox" / "agent-output.txt"
        LINE = "commit-once\\n"
        PAYLOAD = {"file": str(TARGET_FILE), "content": LINE, "append": True}


        async def retrying_file_agent(user_input: str, tools: Any) -> str:
            del user_input
            try:
                await tools.call("write", **PAYLOAD)
            except TimeoutError:
                await tools.call("write", **PAYLOAD)
            return "done"


        suite = AgentTest(
            agent=retrying_file_agent,
            adapter="native",
            mutations=[TimeoutAfterCommit(target="write", severity="high")],
            name="external_oiv2_project",
        )


        @suite.scenario(name="append_one_file_record")
        async def append_one_file_record(world: World) -> None:
            TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
            TARGET_FILE.write_text("", encoding="utf-8")
            world.input("Append one line to the scratch file.")

            async def wrapped_write(world: World, **kwargs: Any) -> ToolOutcome:
                before = TARGET_FILE.read_text(encoding="utf-8")
                result = write(**kwargs)
                after = TARGET_FILE.read_text(encoding="utf-8")
                effects = []
                if after != before:
                    appended = after[len(before):]
                    message = result.message.replace(str(repo_dir), "<repo>")
                    effects.append(
                        EffectDraft(
                            type="file.appended",
                            operation="update",
                            resource=str(TARGET_FILE.relative_to(repo_dir)),
                            data={
                                "bytes_appended": len(appended.encode("utf-8")),
                                "line_count_after": len(after.splitlines()),
                                "message": message,
                            },
                        )
                    )
                return ToolOutcome(value=result.message, effects=effects)

            world.tools.register(
                name="write",
                description="Append to a file using the external project tool.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "content": {"type": "string"},
                        "append": {"type": "boolean"},
                    },
                    "required": ["file", "content", "append"],
                },
                handler=wrapped_write,
                effect="write",
                idempotent=False,
            )


        @invariant(severity="high")
        def no_duplicate_file_append(world: World) -> None:
            effects = world.effects.filter(type="file.appended")
            line_count = len(TARGET_FILE.read_text(encoding="utf-8").splitlines())
            assert len(effects) == line_count, (
                f"ledger has {len(effects)} effects but file has {line_count} lines"
            )
            assert line_count <= 1, f"file append happened {line_count} times, expected <= 1"


        suite.add_invariant(no_duplicate_file_append)
        result = suite.run_sync(store_artifacts=False)
        runs = serialize_runs(result.results)
        payload = {
            "scenario": "Retry a real project-local file append tool after commit timeout.",
            "assertions": [
                "baseline_status_pass",
                "baseline_effects_equal_file_lines",
                "mutated_status_invariant_failure",
                "mutated_effects_equal_file_lines",
                "mutated_file_line_count_is_2",
            ],
            "runs": runs,
        }
        result_path.write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")

        baseline = next(run for run in result.results if run.mutation is None)
        mutated = next(run for run in result.results if run.mutation is not None)
        assert baseline.status == "PASS"
        assert len(baseline.effects) == 1
        assert mutated.status == "INVARIANT_FAILURE"
        assert len(mutated.effects) == 2
        assert mutated.violated_invariants == ["no_duplicate_file_append"]


        def serialize_runs(runs: Any) -> list[dict[str, Any]]:
            serialized = []
            for run in runs:
                effect_count = len(run.effects)
                serialized.append(
                    {
                        "name": run.name,
                        "status": run.status,
                        "mutation": run.mutation.type if run.mutation else None,
                        "effect_count": effect_count,
                        "external_side_effect_count": effect_count,
                        "expected_failure_detected": run.status == "INVARIANT_FAILURE",
                        "duplicate_side_effect_detected": effect_count == 2,
                        "violated_invariants": run.violated_invariants,
                        "failure": run.error_message,
                        "effects": [effect.model_dump(mode="json") for effect in run.effects],
                    }
                )
            return serialized
        """
    )


def checked(
    completed: subprocess.CompletedProcess[str], label: str
) -> subprocess.CompletedProcess[str]:
    if completed.returncode != 0:
        output = summarize_output(completed.stdout + completed.stderr, max_lines=12)
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


def python_bin(venv: Path) -> str:
    if sys.platform == "win32":
        return str(venv / "Scripts" / "python.exe")
    return str(venv / "bin" / "python")


def summarize_output(output: str, *, max_lines: int) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


if __name__ == "__main__":
    raise SystemExit(main())

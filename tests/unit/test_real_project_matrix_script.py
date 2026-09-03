from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType


def load_real_project_matrix() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "real_project_matrix.py"
    spec = importlib.util.spec_from_file_location("real_project_matrix", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_project_matrix_metadata_is_pinned_and_auditable() -> None:
    module = load_real_project_matrix()
    keys = [project.key for project in module.INCLUDED_PROJECTS]

    assert len(keys) == len(set(keys))
    assert len(module.INCLUDED_PROJECTS) >= 3
    for project in module.INCLUDED_PROJECTS:
        assert project.repo_url.startswith("https://github.com/")
        assert re.fullmatch(r"[0-9a-f]{40}", project.ref)
        assert project.framework_boundary
        assert project.side_effect
        assert project.expected_signal

    assert module.REJECTED_PROJECTS
    for project in module.REJECTED_PROJECTS:
        assert project["repo_url"].startswith("https://github.com/")
        assert re.fullmatch(r"[0-9a-f]{40}", project["ref"])
        assert project["reason"]


def test_summary_counts_only_truthful_run_fields() -> None:
    module = load_real_project_matrix()
    results = [
        {
            "runs": [
                {
                    "status": "PASS",
                    "effect_count": 1,
                    "expected_failure_detected": False,
                    "duplicate_side_effect_detected": False,
                },
                {
                    "status": "INVARIANT_FAILURE",
                    "effect_count": 2,
                    "expected_failure_detected": True,
                    "duplicate_side_effect_detected": True,
                },
            ]
        },
        {
            "runs": [
                {
                    "status": "PASS",
                    "effect_count": 1,
                    "expected_failure_detected": False,
                    "duplicate_side_effect_detected": False,
                }
            ]
        },
    ]

    assert module.summarize(results) == {
        "projects_tested": 2,
        "agentproof_runs": 3,
        "invariant_failures": 1,
        "expected_failures_detected": 1,
        "duplicate_side_effects_detected": 1,
        "effects_recorded": 4,
    }


def test_generated_harness_sources_are_valid_python() -> None:
    module = load_real_project_matrix()

    for project in module.INCLUDED_PROJECTS:
        source = module.harness_source(project.key)
        compile(source, f"<{project.key}>", "exec")

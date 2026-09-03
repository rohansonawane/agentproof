from __future__ import annotations

import asyncio
import importlib.util
import sys
from contextlib import suppress
from pathlib import Path
from types import ModuleType

from agentproof.api import AgentTest
from agentproof.core.result import SuiteResult
from agentproof.mutations import mutation_from_spec
from agentproof.replay.schema import RUN_ARTIFACT_SCHEMA_VERSION, RunArtifact


def load_artifact(path: str | Path) -> RunArtifact:
    artifact = RunArtifact.model_validate_json(Path(path).read_text(encoding="utf-8"))
    if artifact.schema_version != RUN_ARTIFACT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported artifact schema {artifact.schema_version}; "
            f"expected {RUN_ARTIFACT_SCHEMA_VERSION}"
        )
    return artifact


async def replay_artifact(path: str | Path) -> SuiteResult:
    artifact = load_artifact(path)
    source_path = artifact.metadata.get("source_path")
    suite_name = artifact.metadata.get("suite_name")
    if not isinstance(source_path, str):
        raise ValueError("artifact does not contain metadata.source_path for deterministic replay")
    suite = _load_suite(Path(source_path), suite_name if isinstance(suite_name, str) else None)
    mutation = mutation_from_spec(artifact.mutation) if artifact.mutation else None
    return await suite.run(
        scenario=artifact.scenario,
        mutations=[] if mutation is None else [mutation],
        seed=artifact.seed,
        artifacts_dir=Path(path).parent / "replay",
        store_artifacts=False,
        source_path=source_path,
        suite_name=suite_name if isinstance(suite_name, str) else None,
    )


def replay_artifact_sync(path: str | Path) -> SuiteResult:
    return asyncio.run(replay_artifact(path))


def _load_suite(source_path: Path, suite_name: str | None) -> AgentTest:
    module = _load_module_from_path(source_path)
    suites = [
        (name, value)
        for name, value in vars(module).items()
        if isinstance(value, AgentTest) and (suite_name is None or name == suite_name)
    ]
    if not suites:
        raise ValueError(f"no AgentTest suite found in {source_path}")
    return suites[0][1]


def _load_module_from_path(source_path: Path) -> ModuleType:
    module_name = f"agentproof_replay_{abs(hash(source_path))}"
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import {source_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    sys.path.insert(0, str(source_path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        with suppress(ValueError):
            sys.path.remove(str(source_path.parent))
    return module

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path

from agentproof.core.redaction import redact
from agentproof.core.result import RunResult
from agentproof.replay.schema import RunArtifact


def write_repro_artifact(result: RunResult, artifacts_dir: Path) -> Path:
    run_dir = artifacts_dir / result.run_id
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    artifact = RunArtifact(
        run_id=result.run_id,
        scenario=result.scenario,
        seed=result.seed,
        mutation=result.mutation,
        initial_world_snapshot=redact(result.initial_world_snapshot),
        trace=result.trace,
        violated_invariants=result.violated_invariants,
        metadata=redact(result.metadata),
    )
    path = run_dir / "repro.json"
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    with suppress(OSError):
        os.chmod(path, 0o600)
    return path

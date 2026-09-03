from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentproof.core.redaction import redact
from agentproof.core.result import SuiteResult


def suite_to_json(result: SuiteResult) -> dict[str, Any]:
    return redact(
        {
            "schema_version": result.schema_version,
            "run_id": result.run_id,
            "summary": {
                "total": result.total_count,
                "passed": result.passed_count,
                "failed": result.failed_count,
            },
            "results": [
                {
                    "name": item.name,
                    "scenario": item.scenario,
                    "adapter": item.adapter,
                    "seed": item.seed,
                    "mutation": item.mutation.model_dump(mode="json") if item.mutation else None,
                    "severity": item.severity,
                    "status": item.status,
                    "violated_invariants": item.violated_invariants,
                    "invariant_failures": [
                        failure.model_dump(mode="json") for failure in item.invariant_failures
                    ],
                    "error_message": item.error_message,
                    "effects": [effect.model_dump(mode="json") for effect in item.effects],
                    "trace": [event.model_dump(mode="json") for event in item.trace],
                    "artifact_path": str(item.artifact_path) if item.artifact_path else None,
                }
                for item in result.results
            ],
            "metadata": result.metadata,
        }
    )


def write_json_report(result: SuiteResult, path: str | Path) -> None:
    Path(path).write_text(json.dumps(suite_to_json(result), indent=2), encoding="utf-8")

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentproof.core.effects import Effect
from agentproof.core.faults import MutationSpec, Severity
from agentproof.core.trace import TraceEvent

RunStatus = Literal[
    "PASS",
    "INVARIANT_FAILURE",
    "BASELINE_FAILURE",
    "AGENT_ERROR",
    "TOOL_ERROR_EXPECTED",
    "TEST_ERROR",
    "ADAPTER_ERROR",
    "UNSUPPORTED",
    "SKIPPED",
]

SEVERITY_ORDER: dict[Severity, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class InvariantFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    message: str
    exception_type: str
    traceback: str


class RunResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    scenario: str
    adapter: str
    seed: int
    mutation: MutationSpec | None = None
    severity: Severity = "medium"
    status: RunStatus = "PASS"
    final_output: str | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    effects: list[Effect] = Field(default_factory=list)
    violated_invariants: list[str] = Field(default_factory=list)
    invariant_failures: list[InvariantFailure] = Field(default_factory=list)
    error_message: str | None = None
    artifact_path: Path | None = None
    initial_world_snapshot: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.status in {
            "INVARIANT_FAILURE",
            "BASELINE_FAILURE",
            "AGENT_ERROR",
            "TEST_ERROR",
            "ADAPTER_ERROR",
            "UNSUPPORTED",
        }

    @property
    def name(self) -> str:
        if self.mutation is None:
            return f"{self.scenario}:baseline"
        target = f":{self.mutation.target}" if self.mutation.target else ""
        return f"{self.scenario}:{self.mutation.type}{target}"


class SuiteResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_version: int = 1
    run_id: str
    results: list[RunResult]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def failures(self) -> list[RunResult]:
        return [result for result in self.results if result.failed]

    @property
    def failed_count(self) -> int:
        return len(self.failures)

    @property
    def passed_count(self) -> int:
        return len([result for result in self.results if result.status == "PASS"])

    @property
    def total_count(self) -> int:
        return len(self.results)

    def exit_code(self, fail_on: Severity = "high") -> int:
        threshold = SEVERITY_ORDER[fail_on]
        for result in self.failures:
            if SEVERITY_ORDER[result.severity] >= threshold:
                return 1
        return 0

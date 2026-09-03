from __future__ import annotations

import inspect
import uuid
from pathlib import Path
from typing import Any

from agentproof.adapters.base import AgentRunResult
from agentproof.core.faults import AgentProofError, MutationSpec, UnsupportedMutationError
from agentproof.core.invariant import Invariant, evaluate_invariants
from agentproof.core.result import InvariantFailure, RunResult, SuiteResult
from agentproof.core.scenario import Scenario
from agentproof.core.world import World
from agentproof.mutations.base import Mutation
from agentproof.replay.recorder import write_repro_artifact


class ScenarioRunner:
    def __init__(
        self,
        *,
        adapter: Any,
        scenarios: list[Scenario],
        invariants: list[Invariant],
        mutations: list[Mutation],
    ) -> None:
        self.adapter = adapter
        self.scenarios = scenarios
        self.invariants = invariants
        self.mutations = mutations

    async def run(
        self,
        *,
        scenario: str | None = None,
        mutations: list[Mutation] | None = None,
        mutation_name: str | None = None,
        seed: int = 42,
        artifacts_dir: Path = Path(".agentproof/runs"),
        store_artifacts: bool = True,
        source_path: str | None = None,
        suite_name: str | None = None,
    ) -> SuiteResult:
        selected_scenarios = [item for item in self.scenarios if scenario in (None, item.name)]
        if not selected_scenarios:
            raise ValueError(f"unknown scenario: {scenario}")

        suite_run_id = f"ap_{uuid.uuid4().hex[:12]}"
        results: list[RunResult] = []
        for scenario_item in selected_scenarios:
            baseline = await self._run_one(
                scenario=scenario_item,
                mutation=None,
                seed=seed,
                suite_run_id=suite_run_id,
                artifacts_dir=artifacts_dir,
                store_artifacts=store_artifacts,
                source_path=source_path,
                suite_name=suite_name,
            )
            results.append(baseline)
            if baseline.status != "PASS":
                continue

            candidate_mutations = mutations if mutations is not None else self.mutations
            for mutation in candidate_mutations:
                if mutation_name is not None and mutation.spec.type != mutation_name:
                    continue
                expanded = await self._expand_mutation(scenario_item, mutation, seed)
                for item in expanded:
                    results.append(
                        await self._run_one(
                            scenario=scenario_item,
                            mutation=item,
                            seed=seed,
                            suite_run_id=suite_run_id,
                            artifacts_dir=artifacts_dir,
                            store_artifacts=store_artifacts,
                            source_path=source_path,
                            suite_name=suite_name,
                        )
                    )
        return SuiteResult(
            run_id=suite_run_id,
            results=results,
            metadata={"source_path": source_path, "suite_name": suite_name},
        )

    async def _expand_mutation(
        self,
        scenario: Scenario,
        mutation: Mutation,
        seed: int,
    ) -> list[Mutation]:
        if mutation.target is not None or mutation.spec.type in {
            "duplicate_user_request",
            "delayed_event",
            "duplicate_event",
            "reorder_tool_results",
        }:
            return [mutation]
        world = World(seed=seed)
        await _maybe_await(scenario.func(world))
        tools = world.tools.all()
        if not tools:
            return [mutation]
        result: list[Mutation] = []
        for tool in tools:
            if mutation.spec.type == "timeout_after_commit" and tool.effect not in {
                "write",
                "delete",
                "external",
                "financial",
                "privileged",
            }:
                continue
            result.append(
                type(mutation)(
                    target=tool.name,
                    occurrence=mutation.occurrence,
                    params=mutation.params,
                    severity=mutation.severity,
                )
            )
        return result or [mutation]

    async def _run_one(
        self,
        *,
        scenario: Scenario,
        mutation: Mutation | None,
        seed: int,
        suite_run_id: str,
        artifacts_dir: Path,
        store_artifacts: bool,
        source_path: str | None,
        suite_name: str | None,
    ) -> RunResult:
        world = World(seed=seed, metadata={"source_path": source_path, "suite_name": suite_name})
        run_id = world.next_id("run")
        run_id = f"{suite_run_id}_{run_id}"
        status = "PASS"
        output: str | None = None
        error_message: str | None = None
        invariant_failures: list[InvariantFailure] = []
        invariant_errors: list[InvariantFailure] = []
        initial_snapshot: dict[str, Any] = {}

        try:
            await _maybe_await(scenario.func(world))
            initial_snapshot = world.snapshot()
            if mutation is not None:
                mutation.install(world)
            inputs = world.faults.prepare_user_inputs(world.user_inputs)
            for user_input in inputs:
                adapter_result = await self.adapter.run(world=world, user_input=user_input)
                output = _stringify_output(adapter_result)
                world.trace.record(
                    "agent_output",
                    getattr(self.adapter, "name", type(self.adapter).__name__),
                    {"output": output, "metadata": getattr(adapter_result, "metadata", {})},
                )
        except UnsupportedMutationError as exc:
            status = "UNSUPPORTED"
            error_message = str(exc)
        except AgentProofError as exc:
            status = "AGENT_ERROR"
            error_message = str(exc)
        except Exception as exc:
            status = "AGENT_ERROR"
            error_message = f"{type(exc).__name__}: {exc}"

        if status == "PASS":
            invariant_failures, invariant_errors = await evaluate_invariants(self.invariants, world)
            if invariant_errors:
                status = "TEST_ERROR"
                error_message = invariant_errors[0].message
            elif invariant_failures:
                status = "BASELINE_FAILURE" if mutation is None else "INVARIANT_FAILURE"
                error_message = invariant_failures[0].message

        mutation_spec: MutationSpec | None = mutation.spec if mutation is not None else None
        result = RunResult(
            run_id=run_id,
            scenario=scenario.name,
            adapter=getattr(self.adapter, "name", type(self.adapter).__name__),
            seed=seed,
            mutation=mutation_spec,
            severity=mutation_spec.severity if mutation_spec else "high",
            status=status,  # type: ignore[arg-type]
            final_output=output,
            trace=world.trace.all(),
            effects=world.effects.all(),
            violated_invariants=[failure.name for failure in invariant_failures],
            invariant_failures=invariant_failures + invariant_errors,
            error_message=error_message,
            initial_world_snapshot=initial_snapshot,
            metadata={"source_path": source_path, "suite_name": suite_name},
        )
        if store_artifacts and result.failed:
            result.artifact_path = write_repro_artifact(result, artifacts_dir)
        return result


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _stringify_output(adapter_result: AgentRunResult | Any) -> str | None:
    if isinstance(adapter_result, AgentRunResult):
        return adapter_result.final_output
    if adapter_result is None:
        return None
    return str(adapter_result)

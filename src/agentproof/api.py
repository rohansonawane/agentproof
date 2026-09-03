from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

from agentproof.adapters.native import NativeAdapter
from agentproof.core.invariant import Invariant
from agentproof.core.result import SuiteResult
from agentproof.core.runner import ScenarioRunner
from agentproof.core.scenario import Scenario, ScenarioFunc
from agentproof.mutations.base import Mutation


class AgentTest:
    def __init__(
        self,
        *,
        agent: Any,
        adapter: str | Any = "native",
        mutations: list[Mutation] | None = None,
        invariants: list[Invariant] | None = None,
        name: str | None = None,
    ) -> None:
        self.name = name or "agentproof_suite"
        self.agent = agent
        self.adapter = self._coerce_adapter(adapter, agent)
        self.mutations = list(mutations or [])
        self.invariants = list(invariants or [])
        self.scenarios: list[Scenario] = []

    def scenario(self, func: ScenarioFunc | None = None, *, name: str | None = None) -> Any:
        def wrap(inner: ScenarioFunc) -> ScenarioFunc:
            self.scenarios.append(Scenario(name=name or inner.__name__, func=inner))
            return inner

        if func is None:
            return wrap
        return wrap(func)

    def add_invariant(self, item: Invariant) -> Invariant:
        self.invariants.append(item)
        return item

    async def run(
        self,
        *,
        scenario: str | None = None,
        mutations: list[Mutation] | None = None,
        mutation_name: str | None = None,
        seed: int = 42,
        artifacts_dir: str | Path = ".agentproof/runs",
        store_artifacts: bool = True,
        source_path: str | None = None,
        suite_name: str | None = None,
    ) -> SuiteResult:
        runner = ScenarioRunner(
            adapter=self.adapter,
            scenarios=self.scenarios,
            invariants=self._all_invariants(),
            mutations=self.mutations,
        )
        return await runner.run(
            scenario=scenario,
            mutations=mutations,
            mutation_name=mutation_name,
            seed=seed,
            artifacts_dir=Path(artifacts_dir),
            store_artifacts=store_artifacts,
            source_path=source_path,
            suite_name=suite_name or self.name,
        )

    def run_sync(self, **kwargs: Any) -> SuiteResult:
        return asyncio.run(self.run(**kwargs))

    def _all_invariants(self) -> list[Invariant]:
        discovered: list[Invariant] = []
        for scenario in self.scenarios:
            module = inspect.getmodule(scenario.func)
            if module is None:
                continue
            for value in vars(module).values():
                if isinstance(value, Invariant) and value not in discovered:
                    discovered.append(value)
        result = list(self.invariants)
        for item in discovered:
            if item not in result:
                result.append(item)
        return result

    @staticmethod
    def _coerce_adapter(adapter: str | Any, agent: Any) -> Any:
        if adapter == "native":
            return NativeAdapter(agent)
        if isinstance(adapter, NativeAdapter) and adapter.agent is None:
            adapter.agent = agent
        return adapter

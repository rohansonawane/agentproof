from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from agentproof.api import AgentTest
from agentproof.core.effects import Effect, EffectDraft
from agentproof.core.faults import MutationSpec
from agentproof.core.invariant import Invariant, invariant
from agentproof.core.result import RunResult, SuiteResult
from agentproof.core.scenario import Scenario
from agentproof.core.trace import TraceEvent
from agentproof.core.world import World
from agentproof.mutations.base import Mutation

try:
    __version__ = version("agentproof")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "AgentTest",
    "Effect",
    "EffectDraft",
    "Invariant",
    "Mutation",
    "MutationSpec",
    "RunResult",
    "Scenario",
    "SuiteResult",
    "TraceEvent",
    "World",
    "__version__",
    "invariant",
]

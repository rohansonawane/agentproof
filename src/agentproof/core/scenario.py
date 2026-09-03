from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

ScenarioFunc = Callable[[Any], Awaitable[None] | None]


@dataclass(frozen=True)
class Scenario:
    name: str
    func: ScenarioFunc

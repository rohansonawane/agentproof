from __future__ import annotations

import inspect
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agentproof.core.result import InvariantFailure

InvariantFunc = Callable[[Any], Awaitable[None] | None]


@dataclass(frozen=True)
class Invariant:
    name: str
    func: InvariantFunc
    severity: str = "high"

    async def check(self, world: Any) -> InvariantFailure | None:
        try:
            result = self.func(world)
            if inspect.isawaitable(result):
                await result
        except AssertionError as exc:
            return InvariantFailure(
                name=self.name,
                message=str(exc) or "assertion failed",
                exception_type=type(exc).__name__,
                traceback="".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__, limit=6)
                ),
            )
        return None

    async def check_programming_error(self, world: Any) -> InvariantFailure | None:
        try:
            result = self.func(world)
            if inspect.isawaitable(result):
                await result
        except AssertionError:
            raise
        except Exception as exc:
            return InvariantFailure(
                name=self.name,
                message=str(exc),
                exception_type=type(exc).__name__,
                traceback="".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__, limit=6)
                ),
            )
        return None


def invariant(
    func: InvariantFunc | None = None, *, name: str | None = None, severity: str = "high"
) -> Any:
    def wrap(inner: InvariantFunc) -> Invariant:
        return Invariant(name=name or inner.__name__, func=inner, severity=severity)

    if func is None:
        return wrap
    return wrap(func)


async def evaluate_invariants(
    invariants: list[Invariant],
    world: Any,
) -> tuple[list[InvariantFailure], list[InvariantFailure]]:
    assertion_failures: list[InvariantFailure] = []
    programming_errors: list[InvariantFailure] = []
    for item in invariants:
        try:
            result = item.func(world)
            if inspect.isawaitable(result):
                await result
        except AssertionError as exc:
            failure = InvariantFailure(
                name=item.name,
                message=str(exc) or "assertion failed",
                exception_type=type(exc).__name__,
                traceback="".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__, limit=6)
                ),
            )
            assertion_failures.append(failure)
            world.trace.record(
                "invariant_fail",
                item.name,
                {"message": failure.message, "exception_type": failure.exception_type},
            )
        except Exception as exc:
            failure = InvariantFailure(
                name=item.name,
                message=str(exc),
                exception_type=type(exc).__name__,
                traceback="".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__, limit=6)
                ),
            )
            programming_errors.append(failure)
            world.trace.record(
                "invariant_fail",
                item.name,
                {"message": failure.message, "exception_type": failure.exception_type},
            )
        else:
            world.trace.record("invariant_pass", item.name, {})
    return assertion_failures, programming_errors

from __future__ import annotations

from typing import Any


class ToolClient:
    def __init__(self, world: Any) -> None:
        self._world = world

    async def call(self, name: str, **kwargs: Any) -> Any:
        return await self._world.tools.invoke(name, kwargs)

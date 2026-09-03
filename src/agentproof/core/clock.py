from __future__ import annotations


class VirtualClock:
    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        self._now += float(seconds)
        return self._now

    def set(self, timestamp: float) -> None:
        self._now = float(timestamp)

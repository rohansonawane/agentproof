from __future__ import annotations

from agentproof import World
from agentproof.core.redaction import REDACTED


def test_trace_redacts_secret_keys_and_secret_like_strings() -> None:
    world = World(seed=1)
    world.trace.record(
        "tool_call",
        "secret_tool",
        {
            "api_key": "sk-test",
            "nested": {"authorization": "Bearer abc", "safe": "visible"},
            "list": [{"token": "abc"}],
            "string_secret": "sk-live-secret",
        },
    )

    data = world.trace.all()[0].data
    assert data["api_key"] == REDACTED
    assert data["nested"]["authorization"] == REDACTED
    assert data["nested"]["safe"] == "visible"
    assert data["list"][0]["token"] == REDACTED
    assert data["string_secret"] == REDACTED


def test_snapshot_redacts_metadata_secrets() -> None:
    world = World(seed=1, metadata={"password": "abc", "name": "demo"})

    snapshot = world.snapshot()

    assert snapshot["metadata"]["password"] == REDACTED
    assert snapshot["metadata"]["name"] == "demo"

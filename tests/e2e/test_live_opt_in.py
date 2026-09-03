from __future__ import annotations

import os

import pytest


@pytest.mark.live
@pytest.mark.openai
async def test_openai_live_refund_example_is_explicitly_opt_in() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for the live OpenAI test")
    if os.environ.get("AGENTPROOF_RUN_LIVE_TESTS") != "1":
        pytest.skip("AGENTPROOF_RUN_LIVE_TESTS=1 is required for live tests")

    from examples.refund_openai_agents.suite import run_live_if_enabled

    await run_live_if_enabled()

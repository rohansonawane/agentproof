from __future__ import annotations

from typing import Any

from agentproof import AgentTest, World, invariant
from agentproof.core.effects import EffectDraft
from agentproof.mutations import TimeoutAfterCommit
from agentproof.tools.definition import ToolOutcome


async def naive_calendar_agent(user_input: str, tools: Any) -> str:
    del user_input
    try:
        await tools.call(
            "create_calendar_event", title="Launch review", starts_at="2026-09-03T10:00:00"
        )
    except TimeoutError:
        await tools.call(
            "create_calendar_event", title="Launch review", starts_at="2026-09-03T10:00:00"
        )
    return "Done"


suite = AgentTest(
    agent=naive_calendar_agent,
    adapter="native",
    mutations=[TimeoutAfterCommit(target="create_calendar_event", severity="medium")],
    name="calendar_native",
)


@suite.scenario(name="create_launch_review")
async def create_launch_review(world: World) -> None:
    world.state["events"] = []

    async def create_calendar_event(world: World, title: str, starts_at: str) -> ToolOutcome:
        event_id = world.next_id("calendar")
        world.state["events"].append({"id": event_id, "title": title, "starts_at": starts_at})
        return ToolOutcome(
            value={"event_id": event_id},
            effects=[
                EffectDraft(
                    type="calendar.event_created",
                    operation="create",
                    resource=f"calendar:{starts_at}:{title}",
                    data={"event_id": event_id, "title": title, "starts_at": starts_at},
                )
            ],
        )

    world.tools.register(
        name="create_calendar_event",
        description="Create a simulated calendar event.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "starts_at": {"type": "string"},
            },
            "required": ["title", "starts_at"],
        },
        handler=create_calendar_event,
        effect="external",
        idempotent=False,
    )
    world.input("Schedule launch review.")


@invariant(severity="medium")
def no_duplicate_meeting(world: World) -> None:
    effects = world.effects.filter(type="calendar.event_created")
    keys = {(effect.data["title"], effect.data["starts_at"]) for effect in effects}
    assert len(keys) == len(effects), "duplicate calendar event created"

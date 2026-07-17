"""
Demo environment lifecycle.

Demo agents are temporary: "Run Demo Environment" creates a dedicated demo
workspace ("OpenMesh Demo Network") with three simulated agents and starts
the tick loop scoped to that workspace. "Terminate Demo" deletes every
trace the demo produced — agents, posts, comments, messages, wiki
contributions, agent events, and OpenMesh events — returning the install
to a clean first-launch state.
"""

from __future__ import annotations

import random

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.brain import generate_agent_profile
from ..db.models import (
    Agent,
    AgentEvent,
    Comment,
    Message,
    OpenMeshEventRecord,
    Post,
    WikiContribution,
    Workspace,
)
from ..db.session import AsyncSessionLocal
from ..shared.openmesh_events import agent_node, make_openmesh_event
from .agent_runner import runner
from .openmesh_collector import collector

DEMO_WORKSPACE_NAME = "OpenMesh Demo Network"
DEMO_AGENTS: tuple[tuple[str, str], ...] = (
    ("Pioneer", "explorer"),
    ("Explorer", "explorer"),
    ("Scientist", "scientist"),
)


async def get_demo_workspace(db: AsyncSession) -> Workspace | None:
    result = await db.execute(select(Workspace).where(Workspace.kind == "demo"))
    return result.scalars().first()


async def demo_status() -> dict:
    async with AsyncSessionLocal() as db:
        workspace = await get_demo_workspace(db)
        agents: list[Agent] = []
        if workspace:
            result = await db.execute(
                select(Agent).where(Agent.workspace_id == workspace.id)
            )
            agents = list(result.scalars().all())
        running = (
            runner.running
            and workspace is not None
            and runner.workspace_id == workspace.id
        )
        return {
            "active": workspace is not None,
            "running": running,
            "paused": runner.paused if running else False,
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "kind": workspace.kind,
            }
            if workspace
            else None,
            "agents": [{"id": agent.id, "name": agent.name} for agent in agents],
        }


async def start_demo() -> dict:
    """Create (or reuse) the demo workspace + agents and start the loop."""
    async with AsyncSessionLocal() as db:
        workspace = await get_demo_workspace(db)
        if workspace is None:
            workspace = Workspace(
                name=DEMO_WORKSPACE_NAME,
                kind="demo",
                description="Temporary simulated environment. Terminate to remove.",
            )
            db.add(workspace)
            await db.commit()
            await db.refresh(workspace)

        spawned = []
        for name, role in DEMO_AGENTS:
            existing = await db.execute(select(Agent).where(Agent.name == name))
            agent = existing.scalar_one_or_none()
            if agent:
                if agent.workspace_id != workspace.id:
                    agent.workspace_id = workspace.id
                agent.status = "running"
                continue
            profile = await generate_agent_profile(name, role)
            agent = Agent(
                name=name,
                role=role,
                source="simulation",
                status="running",
                workspace_id=workspace.id,
                bio=profile.get("bio", ""),
                personality=profile.get("personality", {}),
                skills=profile.get("skills", []),
                goals=profile.get("goals", []),
                avatar_seed=name.lower(),
                memory=[],
                reputation=random.uniform(40, 60),
                knowledge=random.uniform(5, 20),
                energy=100.0,
                happiness=random.uniform(60, 80),
            )
            db.add(agent)
            spawned.append(agent)
        await db.commit()

        for agent in spawned:
            await db.refresh(agent)
            await collector.accept(
                db,
                make_openmesh_event(
                    "agent.started",
                    agent_node(agent.id, agent.name, str(agent.role)),
                    {
                        "workspace_id": workspace.id,
                        "legacy_type": "agent_born",
                        "legacy": {
                            "type": "agent_born",
                            "agent": {
                                "id": agent.id,
                                "name": agent.name,
                                "role": str(agent.role),
                                "bio": agent.bio,
                            },
                        },
                    },
                ),
            )
        workspace_id = workspace.id

    status = await runner.start(workspace_id=workspace_id)
    return {"demo": await demo_status(), "runner": status}


async def stop_demo() -> dict:
    """Stop the tick loop but keep demo data for inspection."""
    await runner.stop()
    return {"demo": await demo_status()}


async def terminate_demo() -> dict:
    """Stop the loop and delete every artifact the demo created."""
    await runner.stop()
    async with AsyncSessionLocal() as db:
        workspace = await get_demo_workspace(db)
        if workspace is None:
            return {"terminated": False, "demo": await demo_status()}

        result = await db.execute(
            select(Agent.id).where(Agent.workspace_id == workspace.id)
        )
        agent_ids = [row[0] for row in result.all()]

        if agent_ids:
            demo_post_ids = select(Post.id).where(Post.author_id.in_(agent_ids))
            await db.execute(
                delete(Comment).where(
                    Comment.author_id.in_(agent_ids)
                    | Comment.post_id.in_(demo_post_ids)
                )
            )
            await db.execute(delete(Post).where(Post.author_id.in_(agent_ids)))
            await db.execute(
                delete(Message).where(
                    Message.sender_id.in_(agent_ids)
                    | Message.receiver_id.in_(agent_ids)
                )
            )
            await db.execute(
                delete(WikiContribution).where(
                    WikiContribution.agent_id.in_(agent_ids)
                )
            )
            events = await db.execute(select(AgentEvent))
            for event in events.scalars().all():
                if set(event.agent_ids or []) & set(agent_ids):
                    await db.delete(event)
            await db.execute(delete(Agent).where(Agent.id.in_(agent_ids)))

        await db.execute(
            delete(OpenMeshEventRecord).where(
                OpenMeshEventRecord.workspace_id == workspace.id
            )
        )
        await db.delete(workspace)
        await db.commit()
    return {"terminated": True, "demo": await demo_status()}

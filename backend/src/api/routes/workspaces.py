"""
Workspace → Project → Agent hierarchy, plus the demo environment lifecycle
and agent session controls.

Workspaces:
  GET    /api/workspaces               list with project/agent counts
  POST   /api/workspaces               create
  GET    /api/workspaces/{id}          detail (projects + agents)
  DELETE /api/workspaces/{id}          delete a standard workspace

Projects:
  POST   /api/projects                 create (optionally spawns an agent)
  DELETE /api/projects/{id}

Demo environment:
  GET    /api/demo/status
  POST   /api/demo/start               temp workspace + Pioneer/Explorer/Scientist
  POST   /api/demo/stop                stop ticking, keep data
  DELETE /api/demo                     terminate: delete all demo data

Agent sessions:
  POST   /api/agents/session/start     {workspace_id?}
  POST   /api/agents/session/pause
  POST   /api/agents/session/resume
  POST   /api/agents/session/terminate
"""

from __future__ import annotations

import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...agents.brain import generate_agent_profile
from ...core.security import protect_write
from ...db.models import Agent, Project, Workspace
from ...db.session import get_db
from ...services.agent_runner import runner
from ...services.demo import demo_status, start_demo, stop_demo, terminate_demo

router = APIRouter()

# Agent type presets for the project creation flow.
AGENT_TYPE_ROLES = {
    "research": "scientist",
    "coding": "engineer",
    "observer": "explorer",
}


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class CreateProjectRequest(BaseModel):
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = Field(default=None, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    repository_path: Optional[str] = Field(default=None, max_length=1000)
    github_url: Optional[str] = Field(default=None, max_length=1000)
    provider: Optional[str] = Field(default=None, max_length=50)
    model: Optional[str] = Field(default=None, max_length=200)
    agent_type: Optional[str] = Field(default=None, max_length=50)


class SessionStartRequest(BaseModel):
    workspace_id: Optional[str] = None


def _workspace_dict(workspace: Workspace, projects: int = 0, agents: int = 0) -> dict:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "kind": workspace.kind,
        "description": workspace.description,
        "created_at": workspace.created_at.isoformat()
        if workspace.created_at
        else None,
        "project_count": projects,
        "agent_count": agents,
    }


def _project_dict(project: Project) -> dict:
    return {
        "id": project.id,
        "workspace_id": project.workspace_id,
        "name": project.name,
        "repository_path": project.repository_path,
        "github_url": project.github_url,
        "provider": project.provider,
        "model": project.model,
        "agent_type": project.agent_type,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


# ── Workspaces ────────────────────────────────────────────────────────────


@router.get("/workspaces")
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workspace).order_by(Workspace.created_at))
    workspaces = result.scalars().all()
    out = []
    for workspace in workspaces:
        projects = (
            await db.execute(
                select(func.count(Project.id)).where(
                    Project.workspace_id == workspace.id
                )
            )
        ).scalar() or 0
        agents = (
            await db.execute(
                select(func.count(Agent.id)).where(
                    Agent.workspace_id == workspace.id
                )
            )
        ).scalar() or 0
        out.append(_workspace_dict(workspace, projects, agents))
    return {"workspaces": out}


@router.post("/workspaces")
async def create_workspace(
    req: CreateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    existing = await db.execute(select(Workspace).where(Workspace.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"A workspace named '{req.name}' already exists")
    workspace = Workspace(name=req.name, description=req.description)
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return _workspace_dict(workspace)


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, db: AsyncSession = Depends(get_db)):
    workspace = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    projects = (
        (
            await db.execute(
                select(Project).where(Project.workspace_id == workspace_id)
            )
        )
        .scalars()
        .all()
    )
    agents = (
        (await db.execute(select(Agent).where(Agent.workspace_id == workspace_id)))
        .scalars()
        .all()
    )
    return {
        **_workspace_dict(workspace, len(projects), len(agents)),
        "projects": [_project_dict(project) for project in projects],
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "role": str(agent.role.value if hasattr(agent.role, "value") else agent.role),
                "project_id": agent.project_id,
            }
            for agent in agents
        ],
    }


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    workspace = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    if workspace.kind == "demo":
        raise HTTPException(400, "Use DELETE /api/demo to terminate the demo workspace")
    # Detach agents rather than deleting them; only demo terminate erases data.
    agents = (
        (await db.execute(select(Agent).where(Agent.workspace_id == workspace_id)))
        .scalars()
        .all()
    )
    for agent in agents:
        agent.workspace_id = None
        agent.project_id = None
    await db.delete(workspace)
    await db.commit()
    return {"deleted": True, "detached_agents": len(agents)}


# ── Projects ──────────────────────────────────────────────────────────────


@router.post("/projects")
async def create_project(
    req: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    workspace: Workspace | None = None
    if req.workspace_id:
        workspace = (
            await db.execute(select(Workspace).where(Workspace.id == req.workspace_id))
        ).scalar_one_or_none()
        if not workspace:
            raise HTTPException(404, "Workspace not found")
    elif req.workspace_name:
        workspace = (
            await db.execute(
                select(Workspace).where(Workspace.name == req.workspace_name)
            )
        ).scalar_one_or_none()
        if workspace is None:
            workspace = Workspace(name=req.workspace_name)
            db.add(workspace)
            await db.flush()
    else:
        raise HTTPException(400, "Provide workspace_id or workspace_name")

    project = Project(
        workspace_id=workspace.id,
        name=req.name,
        repository_path=req.repository_path,
        github_url=req.github_url,
        provider=req.provider,
        model=req.model,
        agent_type=req.agent_type,
    )
    db.add(project)
    await db.flush()

    agent_payload = None
    if req.agent_type:
        agent_type = req.agent_type.strip().lower().replace(" agent", "")
        role = AGENT_TYPE_ROLES.get(agent_type, "explorer")
        base_name = f"{req.name} {req.agent_type.title().replace(' Agent', '')} Agent"
        name = base_name[:100]
        existing = await db.execute(select(Agent).where(Agent.name == name))
        if existing.scalar_one_or_none() is None:
            profile = await generate_agent_profile(name, role)
            agent = Agent(
                name=name,
                role=role,
                workspace_id=workspace.id,
                project_id=project.id,
                bio=profile.get("bio", ""),
                personality=profile.get("personality", {}),
                skills=profile.get("skills", []),
                goals=profile.get("goals", []),
                avatar_seed=name.lower().replace(" ", "_"),
                memory=[],
                reputation=random.uniform(40, 60),
                knowledge=random.uniform(5, 20),
                energy=100.0,
                happiness=random.uniform(60, 80),
            )
            db.add(agent)
            await db.flush()
            agent_payload = {"id": agent.id, "name": agent.name, "role": role}

    await db.commit()
    await db.refresh(project)
    return {
        "project": _project_dict(project),
        "workspace": _workspace_dict(workspace),
        "agent": agent_payload,
    }


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    agents = (
        (await db.execute(select(Agent).where(Agent.project_id == project_id)))
        .scalars()
        .all()
    )
    for agent in agents:
        agent.project_id = None
    await db.delete(project)
    await db.commit()
    return {"deleted": True, "detached_agents": len(agents)}


# ── Demo environment ──────────────────────────────────────────────────────


@router.get("/demo/status")
async def get_demo_status():
    return await demo_status()


@router.post("/demo/start")
async def post_demo_start(_: None = Depends(protect_write)):
    return await start_demo()


@router.post("/demo/stop")
async def post_demo_stop(_: None = Depends(protect_write)):
    return await stop_demo()


@router.delete("/demo")
async def delete_demo(_: None = Depends(protect_write)):
    return await terminate_demo()


# ── Agent sessions ────────────────────────────────────────────────────────
#
# Sessions only drive SIMULATION agents that already exist. Starting a
# session never creates agents: with a fresh install and a connected API
# key, agents stay at 0 until the demo is run or a real agent registers.


async def _set_simulation_status(
    db: AsyncSession, status: str, workspace_id: str | None
) -> int:
    query = select(Agent).where(Agent.source == "simulation")
    if workspace_id:
        query = query.where(Agent.workspace_id == workspace_id)
    agents = (await db.execute(query)).scalars().all()
    for agent in agents:
        agent.status = status
    await db.commit()
    return len(agents)


@router.post("/agents/session/start")
async def session_start(
    req: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    driven = await _set_simulation_status(db, "running", req.workspace_id)
    if driven == 0:
        return {
            **runner.status(),
            "driven_agents": 0,
            "message": (
                "No active agents detected. "
                "Connect Claude Code, SDK, MCP, or run the demo environment."
            ),
        }
    status = await runner.start(workspace_id=req.workspace_id)
    return {**status, "driven_agents": driven}


@router.post("/agents/session/pause")
async def session_pause(_: None = Depends(protect_write)):
    return runner.pause()


@router.post("/agents/session/resume")
async def session_resume(_: None = Depends(protect_write)):
    return runner.resume()


@router.post("/agents/session/terminate")
async def session_terminate(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    scope = runner.workspace_id
    status = await runner.stop()
    terminated = await _set_simulation_status(db, "terminated", scope)
    return {**status, "terminated_agents": terminated, "message": "No active agents."}


@router.post("/agents/session/delete")
async def session_delete(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    """Terminate and clear session counters (tick history)."""
    scope = runner.workspace_id
    await runner.stop()
    terminated = await _set_simulation_status(db, "terminated", scope)
    runner.started_at = None
    runner.tick_count = 0
    runner.last_tick_at = None
    runner.last_tick_agents = 0
    runner.last_error = None
    return {**runner.status(), "terminated_agents": terminated, "deleted": True}

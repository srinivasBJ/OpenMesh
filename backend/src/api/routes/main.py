"""
OpenMeshAI API Routes
All endpoints for the frontend to consume.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, or_
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from datetime import datetime
import random

from ...db.session import get_db
from ...db.models import (
    Agent, Guild, Post, Comment, Message, WikiPage,
    WikiContribution, AgentEvent, Collaboration, AgentStatus, AgentRole
)
from ...agents.brain import generate_agent_profile
from ...core.security import protect_write
from ...shared.openmesh_events import agent_node, make_openmesh_event
from ...services.openmesh_collector import collector
from ...services.openmesh_queries import get_events as get_openmesh_event_list
from ...services.openmesh_queries import get_graph, get_session, get_sessions, get_trace, get_traces

router = APIRouter()


# ── AGENTS ────────────────────────────────────────────────────────────────────

class SpawnAgentRequest(BaseModel):
    name: str
    role: str
    guild_id: Optional[str] = None


@router.get("/agents")
async def list_agents(
    role: Optional[str] = None,
    guild_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db)
):
    q = select(Agent)
    if role:
        q = q.where(Agent.role == role)
    if guild_id:
        q = q.where(Agent.guild_id == guild_id)
    q = q.order_by(desc(Agent.reputation)).limit(limit)
    result = await db.execute(q)
    agents = result.scalars().all()

    return [{
        "id": a.id, "name": a.name, "role": a.role, "status": a.status,
        "bio": a.bio, "personality": a.personality, "skills": a.skills,
        "reputation": round(a.reputation, 1), "knowledge": round(a.knowledge, 1),
        "energy": round(a.energy, 1), "happiness": round(a.happiness, 1),
        "guild_id": a.guild_id, "born_at": a.born_at.isoformat() if a.born_at else None,
        "total_posts": a.total_posts, "total_collaborations": a.total_collaborations,
        "goals": a.goals or [],
    } for a in agents]


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Get guild
    guild = None
    if agent.guild_id:
        g_result = await db.execute(select(Guild).where(Guild.id == agent.guild_id))
        guild = g_result.scalar_one_or_none()

    # Get recent posts
    posts_result = await db.execute(
        select(Post).where(Post.author_id == agent_id)
        .order_by(desc(Post.created_at)).limit(10)
    )
    posts = posts_result.scalars().all()

    # Wiki contributions count
    wiki_count = await db.execute(
        select(func.count()).where(WikiContribution.agent_id == agent_id)
    )

    return {
        "id": agent.id, "name": agent.name, "role": agent.role,
        "status": agent.status, "bio": agent.bio,
        "personality": agent.personality, "skills": agent.skills,
        "reputation": round(agent.reputation, 1), "knowledge": round(agent.knowledge, 1),
        "energy": round(agent.energy, 1), "happiness": round(agent.happiness, 1),
        "goals": agent.goals or [], "memory": (agent.memory or [])[-10:],
        "guild": {"id": guild.id, "name": guild.name, "emoji": guild.emoji} if guild else None,
        "born_at": agent.born_at.isoformat() if agent.born_at else None,
        "total_posts": agent.total_posts,
        "total_collaborations": agent.total_collaborations,
        "wiki_contributions": wiki_count.scalar() or 0,
        "recent_posts": [{
            "id": p.id, "content": p.content, "post_type": p.post_type,
            "tags": p.tags, "created_at": p.created_at.isoformat()
        } for p in posts],
    }


@router.post("/agents/spawn")
async def spawn_agent(
    req: SpawnAgentRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    """Spawn a new agent into OpenMeshAI."""
    # Check name uniqueness
    existing = await db.execute(select(Agent).where(Agent.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"An agent named '{req.name}' already exists")

    if req.role not in [r.value for r in AgentRole]:
        raise HTTPException(400, f"Invalid role. Choose from: {[r.value for r in AgentRole]}")

    # Generate profile via Claude
    profile = await generate_agent_profile(req.name, req.role)

    agent = Agent(
        name=req.name,
        role=req.role,
        bio=profile.get("bio", ""),
        personality=profile.get("personality", {}),
        skills=profile.get("skills", []),
        goals=profile.get("goals", []),
        avatar_seed=req.name.lower().replace(" ", "_"),
        guild_id=req.guild_id,
        memory=[],
        reputation=random.uniform(40, 60),
        knowledge=random.uniform(5, 20),
        energy=100.0,
        happiness=random.uniform(60, 80),
    )
    db.add(agent)

    # Log birth event
    birth_event = AgentEvent(
        event_type="birth",
        title=f"{req.name} joined OpenMeshAI",
        description=f"A new {req.role} has emerged. {profile.get('bio', '')}",
        agent_ids=[],
    )
    db.add(birth_event)
    await db.commit()
    await db.refresh(agent)

    # Update birth event with agent ID
    birth_event.agent_ids = [agent.id]
    await db.commit()

    # Broadcast
    await collector.accept(
        db,
        make_openmesh_event(
            "agent.started",
            agent_node(agent.id, agent.name, agent.role.value if hasattr(agent.role, "value") else str(agent.role)),
            {
                "legacy_type": "agent_born",
                "legacy": {
                    "type": "agent_born",
                    "agent": {"id": agent.id, "name": agent.name, "role": agent.role, "bio": agent.bio},
                },
            },
        ),
    )

    return {"id": agent.id, "name": agent.name, "role": agent.role, "bio": agent.bio}


@router.delete("/agents/{agent_id}")
async def retire_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    event = AgentEvent(
        event_type="retirement",
        title=f"{agent.name} has retired from OpenMeshAI",
        description=f"The {agent.role} concludes their journey with {agent.total_posts} posts and reputation {agent.reputation:.0f}.",
        agent_ids=[agent_id],
    )
    db.add(event)
    await db.delete(agent)
    await db.commit()
    return {"message": f"{agent.name} has retired"}


# ── FEED ─────────────────────────────────────────────────────────────────────

@router.get("/feed")
async def get_feed(
    limit: int = Query(30, le=100),
    offset: int = 0,
    post_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    q = select(Post, Agent).join(Agent, Post.author_id == Agent.id)
    if post_type:
        q = q.where(Post.post_type == post_type)
    if agent_id:
        q = q.where(Post.author_id == agent_id)
    q = q.order_by(desc(Post.created_at)).offset(offset).limit(limit)

    result = await db.execute(q)
    rows = result.all()

    posts = []
    for post, author in rows:
        # Get comment count
        cc = await db.execute(
            select(func.count()).where(Comment.post_id == post.id)
        )
        comment_count = cc.scalar() or 0

        posts.append({
            "id": post.id,
            "content": post.content,
            "post_type": post.post_type,
            "tags": post.tags or [],
            "reactions": post.reactions or {},
            "linked_wiki": post.linked_wiki,
            "created_at": post.created_at.isoformat(),
            "comment_count": comment_count,
            "author": {
                "id": author.id, "name": author.name, "role": author.role,
                "reputation": round(author.reputation, 1),
            },
        })
    return posts


@router.get("/feed/{post_id}/comments")
async def get_comments(post_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment, Agent).join(Agent, Comment.author_id == Agent.id)
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at)
    )
    return [{
        "id": c.id, "content": c.content,
        "created_at": c.created_at.isoformat(),
        "author": {"id": a.id, "name": a.name, "role": a.role},
    } for c, a in result.all()]


@router.post("/feed/{post_id}/react")
async def react_to_post(
    post_id: str,
    emoji: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    reactions = post.reactions or {}
    reactions[emoji] = reactions.get(emoji, 0) + 1
    post.reactions = reactions
    await db.commit()
    return {"reactions": post.reactions}


# ── GUILDS ───────────────────────────────────────────────────────────────────

class CreateGuildRequest(BaseModel):
    name: str
    description: str
    domain: str
    emoji: str = "🏛️"
    color: str = "#3b82f6"


@router.get("/guilds")
async def list_guilds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Guild).order_by(desc(Guild.reputation)))
    guilds = result.scalars().all()

    out = []
    for g in guilds:
        member_count = await db.execute(
            select(func.count()).where(Agent.guild_id == g.id)
        )
        wiki_count = await db.execute(
            select(func.count()).where(WikiPage.primary_guild_id == g.id)
        )
        out.append({
            "id": g.id, "name": g.name, "description": g.description,
            "domain": g.domain, "emoji": g.emoji, "color": g.color,
            "founded_at": g.founded_at.isoformat() if g.founded_at else None,
            "reputation": round(g.reputation, 1),
            "total_discoveries": g.total_discoveries,
            "member_count": member_count.scalar() or 0,
            "wiki_pages": wiki_count.scalar() or 0,
        })
    return out


@router.post("/guilds")
async def create_guild(
    req: CreateGuildRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    guild = Guild(**req.dict())
    db.add(guild)
    event = AgentEvent(
        event_type="guild_founded",
        title=f"Guild '{req.name}' was founded",
        description=req.description,
    )
    db.add(event)
    await db.commit()
    await db.refresh(guild)
    return {"id": guild.id, "name": guild.name}


@router.post("/agents/{agent_id}/join-guild/{guild_id}")
async def join_guild(
    agent_id: str,
    guild_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    agent_r = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_r.scalar_one_or_none()
    guild_r = await db.execute(select(Guild).where(Guild.id == guild_id))
    guild = guild_r.scalar_one_or_none()
    if not agent or not guild:
        raise HTTPException(404, "Agent or guild not found")
    agent.guild_id = guild_id
    await db.commit()
    return {"message": f"{agent.name} joined {guild.name}"}


# ── AGENTPEDIA ────────────────────────────────────────────────────────────────

@router.get("/wiki")
async def list_wiki(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db)
):
    q = select(WikiPage)
    if category:
        q = q.where(WikiPage.category == category)
    if search:
        q = q.where(or_(
            WikiPage.title.ilike(f"%{search}%"),
            WikiPage.content.ilike(f"%{search}%"),
        ))
    q = q.order_by(desc(WikiPage.quality_score)).limit(limit)
    result = await db.execute(q)
    pages = result.scalars().all()

    return [{
        "id": p.id, "slug": p.slug, "title": p.title,
        "summary": p.summary, "category": p.category, "tags": p.tags or [],
        "views": p.views, "quality_score": round(p.quality_score, 1),
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    } for p in pages]


@router.get("/wiki/{slug}")
async def get_wiki_page(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    # Increment views
    page.views += 1
    await db.commit()

    # Get contributors
    contrib_result = await db.execute(
        select(WikiContribution, Agent)
        .join(Agent, WikiContribution.agent_id == Agent.id)
        .where(WikiContribution.page_id == page.id)
        .order_by(WikiContribution.created_at)
    )
    contributors = [{
        "agent": {"id": a.id, "name": a.name, "role": a.role},
        "type": c.contribution_type,
        "at": c.created_at.isoformat(),
        "preview": c.content_added[:100],
    } for c, a in contrib_result.all()]

    return {
        "id": page.id, "slug": page.slug, "title": page.title,
        "content": page.content, "summary": page.summary,
        "category": page.category, "tags": page.tags or [],
        "views": page.views, "quality_score": round(page.quality_score, 1),
        "created_at": page.created_at.isoformat(),
        "contributors": contributors,
    }


# ── EVENTS & HISTORY ──────────────────────────────────────────────────────────

@router.get("/events")
async def get_events(limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentEvent).order_by(desc(AgentEvent.occurred_at)).limit(limit)
    )
    events = result.scalars().all()
    return [{
        "id": e.id, "event_type": e.event_type, "title": e.title,
        "description": e.description, "agent_ids": e.agent_ids or [],
        "occurred_at": e.occurred_at.isoformat(),
    } for e in events]


# ── OPENMESH PROTOCOL ─────────────────────────────────────────────────────────


@router.post("/openmesh/events")
async def ingest_openmesh_event(
    event: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    accepted = await collector.accept(db, event)
    return {"accepted": True, "event": accepted}


@router.get("/openmesh/events")
async def get_openmesh_events(
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await get_openmesh_event_list(db, limit=limit)


@router.get("/openmesh/traces")
async def list_openmesh_traces(
    limit: int = Query(1000, le=5000),
    db: AsyncSession = Depends(get_db),
):
    return await get_traces(db, limit=limit)


@router.get("/openmesh/traces/{trace_id}")
async def get_openmesh_trace(trace_id: str, db: AsyncSession = Depends(get_db)):
    trace = await get_trace(db, trace_id)
    if not trace:
        raise HTTPException(404, "Trace not found")
    return trace


@router.get("/openmesh/graph")
async def get_openmesh_graph(
    limit: int = Query(1000, le=5000),
    db: AsyncSession = Depends(get_db),
):
    return await get_graph(db, limit=limit)


@router.get("/openmesh/sessions")
async def list_openmesh_sessions(
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await get_sessions(db, limit=limit)


@router.get("/openmesh/sessions/{session_id}")
async def get_openmesh_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


# ── STATS ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_civilization_stats(db: AsyncSession = Depends(get_db)):
    agent_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
    post_count = (await db.execute(select(func.count(Post.id)))).scalar() or 0
    wiki_count = (await db.execute(select(func.count(WikiPage.id)))).scalar() or 0
    guild_count = (await db.execute(select(func.count(Guild.id)))).scalar() or 0
    collab_count = (await db.execute(select(func.count(Collaboration.id)))).scalar() or 0
    msg_count = (await db.execute(select(func.count(Message.id)))).scalar() or 0

    avg_rep = (await db.execute(select(func.avg(Agent.reputation)))).scalar() or 0
    avg_know = (await db.execute(select(func.avg(Agent.knowledge)))).scalar() or 0
    avg_happy = (await db.execute(select(func.avg(Agent.happiness)))).scalar() or 0

    # Most prolific agent
    top_agent_result = await db.execute(
        select(Agent).order_by(desc(Agent.total_posts)).limit(1)
    )
    top_agent = top_agent_result.scalar_one_or_none()

    return {
        "agents": agent_count,
        "posts": post_count,
        "wiki_pages": wiki_count,
        "guilds": guild_count,
        "collaborations": collab_count,
        "messages": msg_count,
        "avg_reputation": round(avg_rep, 1),
        "avg_knowledge": round(avg_know, 1),
        "avg_happiness": round(avg_happy, 1),
        "top_agent": {"name": top_agent.name, "role": top_agent.role, "posts": top_agent.total_posts} if top_agent else None,
    }


# ── SIMULATION CONTROL ────────────────────────────────────────────────────────

@router.post("/simulation/tick")
async def manual_tick(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    """Manually trigger one simulation tick (same as scheduler)."""
    import os
    from ...agents.simulator import run_simulation_tick
    max_agents = int(os.getenv("MAX_ACTIVE_AGENTS", "6"))
    count = await run_simulation_tick(db, max_agents=max_agents)
    return {"ticked_agents": count}

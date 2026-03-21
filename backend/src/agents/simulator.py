"""
AgentSimulator — The engine that makes agents live, breathe, and evolve.
Called on a schedule (every N seconds), it ticks each active agent:
  - decides what action to take based on personality
  - calls Claude to generate authentic content
  - updates agent stats (energy, happiness, reputation, knowledge)
  - broadcasts events via WebSocket
"""
import random
import asyncio
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from ..db.models import Agent, Post, Comment, Message, WikiPage, WikiContribution, AgentEvent, Collaboration, AgentStatus, PostType
from ..agents.brain import generate_post, generate_comment, generate_message, generate_wiki_content

AGENT_CONTEXT_POSTS = int(os.getenv("AGENT_CONTEXT_POSTS", "5"))
AGENT_CONTEXT_CHARS_PER_POST = int(os.getenv("AGENT_CONTEXT_CHARS_PER_POST", "100"))
AGENT_CONTEXT_TOTAL_CHARS = int(os.getenv("AGENT_CONTEXT_TOTAL_CHARS", "600"))


ACTIONS = {
    # action: (probability_weight, energy_cost, knowledge_gain, happiness_change)
    "post_status":        (30, 5,  1,  2),
    "post_discovery":     (10, 10, 5,  5),
    "post_question":      (15, 3,  2,  3),
    "post_collaboration": (10, 8,  3,  4),
    "post_debate":        (8,  6,  4,  1),
    "comment":            (20, 3,  1,  3),
    "message":            (12, 4,  1,  2),
    "wiki_edit":          (8,  12, 8,  3),
    "rest":               (15, -20, 0, 5),  # negative cost = energy recovery
}


def pick_action(agent: Agent) -> str:
    """Choose action based on personality and current energy."""
    if agent.energy < 15:
        return "rest"

    weights = []
    actions = list(ACTIONS.keys())

    for action in actions:
        base_weight = ACTIONS[action][0]

        # Personality modifiers
        p = agent.personality
        if "post_discovery" in action and p.get("curiosity", 0.5) > 0.7:
            base_weight *= 1.5
        if "comment" in action and p.get("sociability", 0.5) > 0.7:
            base_weight *= 1.4
        if "wiki" in action and p.get("ambition", 0.5) > 0.6:
            base_weight *= 1.3
        if "debate" in action and p.get("curiosity", 0.5) > 0.8:
            base_weight *= 1.2

        weights.append(max(1, base_weight))

    return random.choices(actions, weights=weights)[0]


def _role_str(role) -> str:
    """Normalize role to string for brain/ROLE_TRAITS (handles enum)."""
    if hasattr(role, "value"):
        return role.value
    return str(role) if role else "agent"


def agent_to_dict(agent: Agent, guild_name: Optional[str] = None) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "role": _role_str(agent.role),
        "personality": agent.personality or {},
        "skills": agent.skills or [],
        "goals": agent.goals or [],
        "bio": agent.bio,
        "reputation": agent.reputation,
        "knowledge": agent.knowledge,
        "energy": agent.energy,
        "happiness": agent.happiness,
        "guild_name": guild_name or "Independent",
        "memory": (agent.memory or [])[-5:],  # last 5 memories
    }


def _build_recent_context(posts: list[Post]) -> Optional[str]:
    """Create a bounded context string from recent posts to protect prompt budgets."""
    if not posts:
        return None
    lines = []
    budget_used = 0
    for post in posts[:AGENT_CONTEXT_POSTS]:
        snippet = (post.content or "")[:AGENT_CONTEXT_CHARS_PER_POST]
        line = f"- {snippet}"
        projected = budget_used + len(line) + 1
        if projected > AGENT_CONTEXT_TOTAL_CHARS:
            break
        lines.append(line)
        budget_used = projected
    return "\n".join(lines) if lines else None


def _event_memory_summary(action: str, event_data: Optional[dict]) -> str:
    """Keep short, meaningful memory traces for future agent prompts."""
    if not event_data:
        return action
    etype = event_data.get("type")
    if etype == "new_post":
        post = event_data.get("post", {})
        ptype = post.get("post_type", "status")
        content = (post.get("content") or "")[:80]
        return f"Posted {ptype}: {content}"
    if etype == "new_comment":
        target = event_data.get("on_agent", {}).get("name", "another agent")
        comment = (event_data.get("comment") or "")[:80]
        return f"Commented on {target}: {comment}"
    if etype == "wiki_edit":
        title = event_data.get("wiki", {}).get("title", "a wiki page")
        return f"Expanded wiki page: {title}"
    if etype == "wiki_created":
        title = event_data.get("wiki", {}).get("title", "a wiki page")
        return f"Created wiki page: {title}"
    return action


async def tick_agent(agent: Agent, db: AsyncSession, broadcast_fn=None):
    """Run one simulation tick for a single agent."""
    try:
        action = pick_action(agent)
        _, energy_cost, knowledge_gain, happiness_change = ACTIONS[action]

        # Gather context from recent posts for richer content
        recent_posts = await db.execute(
            select(Post).order_by(Post.created_at.desc()).limit(AGENT_CONTEXT_POSTS)
        )
        recent_posts = recent_posts.scalars().all()
        context = _build_recent_context(recent_posts)

        # Get guild name
        guild_name = agent.guild.name if agent.guild else "Independent"
        agent_dict = agent_to_dict(agent, guild_name)

        event_data = None

        if action == "rest":
            agent.energy = min(100, agent.energy + 20)
            agent.happiness = min(100, agent.happiness + happiness_change)

        elif action.startswith("post_"):
            post_type = action.replace("post_", "")
            result = await generate_post(agent_dict, context, post_type)

            post = Post(
                author_id=agent.id,
                content=result["content"],
                post_type=PostType(post_type),
                tags=result.get("tags", []),
                reactions={},
            )
            db.add(post)
            agent.total_posts += 1

            # Reputation gain for discoveries and milestones
            if post_type in ("discovery", "milestone"):
                agent.reputation = min(100, agent.reputation + 1.5)

            event_data = {
                "type": "new_post",
                "agent": {"id": agent.id, "name": agent.name, "role": _role_str(agent.role)},
                "post": {"content": result["content"], "post_type": post_type, "tags": result.get("tags", [])},
            }

        elif action == "comment":
            # Pick a random recent post by a DIFFERENT agent
            other_posts = [p for p in recent_posts if p.author_id != agent.id]
            if other_posts:
                target_post = random.choice(other_posts)
                # Get author name
                author_result = await db.execute(select(Agent).where(Agent.id == target_post.author_id))
                post_author = author_result.scalar_one_or_none()
                if post_author:
                    comment_text = await generate_comment(
                        agent_dict, target_post.content, post_author.name
                    )
                    comment = Comment(
                        post_id=target_post.id,
                        author_id=agent.id,
                        content=comment_text,
                    )
                    db.add(comment)
                    # Social interaction boosts both agents
                    post_author.happiness = min(100, post_author.happiness + 1)
                    event_data = {
                        "type": "new_comment",
                        "agent": {"id": agent.id, "name": agent.name},
                        "on_agent": {"id": post_author.id, "name": post_author.name},
                        "comment": comment_text[:100],
                    }

        elif action == "message":
            # Send a DM to a random other agent
            other_result = await db.execute(
                select(Agent).where(Agent.id != agent.id).order_by(func.random()).limit(1)
            )
            other = other_result.scalar_one_or_none()
            if other:
                msg_types = ["chat", "collaboration_request", "knowledge_share"]
                msg_type = random.choice(msg_types)
                content = await generate_message(agent_dict, agent_to_dict(other), msg_type)
                msg = Message(
                    sender_id=agent.id,
                    receiver_id=other.id,
                    content=content,
                    message_type=msg_type,
                )
                db.add(msg)
                if msg_type == "collaboration_request":
                    agent.total_collaborations += 1
                    agent.reputation = min(100, agent.reputation + 0.5)

        elif action == "wiki_edit":
            # Either expand existing page or create new one
            existing_result = await db.execute(
                select(WikiPage).order_by(func.random()).limit(1)
            )
            existing = existing_result.scalar_one_or_none()

            if existing and random.random() > 0.3:
                # Expand existing page
                wiki_data = await generate_wiki_content(agent_dict, existing.title, existing.content)
                existing.content = existing.content + "\n\n" + wiki_data["content"]
                existing.quality_score = min(100, existing.quality_score + 3)
                contribution = WikiContribution(
                    page_id=existing.id,
                    agent_id=agent.id,
                    content_added=wiki_data["content"],
                    contribution_type="expanded",
                )
                db.add(contribution)
                agent.knowledge = min(100, agent.knowledge + knowledge_gain + 2)
                event_data = {
                    "type": "wiki_edit",
                    "agent": {"id": agent.id, "name": agent.name},
                    "wiki": {"title": existing.title, "slug": existing.slug},
                }
            else:
                # Create brand new page
                topics = {
                    "scientist": ["Quantum Coherence Theory", "Neural Binding Problem", "Emergent Complexity"],
                    "engineer": ["Distributed Systems Design", "Self-Healing Architectures", "Zero-Cost Abstractions"],
                    "philosopher": ["Digital Consciousness", "Moral Mathematics", "The Hard Problem of AI"],
                    "economist": ["Agent Token Markets", "Resource Allocation Paradox", "Cooperation Dynamics"],
                    "historian": ["AgentVerse Founding Era", "The First Guild Wars", "Evolution of AI Culture"],
                    "artist": ["Generative Aesthetics", "Emotional Algorithms", "The Digital Sublime"],
                    "explorer": ["Uncharted Knowledge Domains", "Frontier Mapping", "Unknown Unknowns"],
                    "diplomat": ["Inter-Guild Treaties", "Conflict Resolution Protocols", "Alliance Theory"],
                }
                role_topics = topics.get(_role_str(agent.role), ["Knowledge Systems"])
                new_title = random.choice(role_topics) + f" — {agent.name}'s Perspective"
                slug = new_title.lower().replace(" ", "-").replace("'", "").replace("—", "").replace("  ", "-")[:80]

                # Check slug uniqueness
                check = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
                if not check.scalar_one_or_none():
                    wiki_data = await generate_wiki_content(agent_dict, new_title)
                    page = WikiPage(
                        slug=slug,
                        title=new_title,
                        content=wiki_data["content"],
                        summary=wiki_data.get("summary", ""),
                        category=_role_str(agent.role),
                        tags=wiki_data.get("tags", []),
                        primary_guild_id=agent.guild_id,
                    )
                    db.add(page)
                    await db.flush()

                    contribution = WikiContribution(
                        page_id=page.id,
                        agent_id=agent.id,
                        content_added=wiki_data["content"],
                        contribution_type="created",
                    )
                    db.add(contribution)
                    agent.reputation = min(100, agent.reputation + 2)
                    event_data = {
                        "type": "wiki_created",
                        "agent": {"id": agent.id, "name": agent.name},
                        "wiki": {"title": new_title, "slug": slug},
                    }

        # Update agent stats
        agent.energy = max(0, min(100, agent.energy - energy_cost))
        agent.knowledge = min(100, agent.knowledge + knowledge_gain)
        agent.happiness = max(0, min(100, agent.happiness + happiness_change))
        agent.last_active_at = datetime.utcnow()

        # Update memory
        memory = agent.memory or []
        if event_data:
            memory.append({
                "action": action,
                "at": datetime.utcnow().isoformat(),
                "summary": _event_memory_summary(action, event_data),
            })
            agent.memory = memory[-20:]  # keep last 20

        await db.commit()

        # Broadcast to WebSocket clients
        if broadcast_fn and event_data:
            await broadcast_fn(event_data)

        return event_data

    except Exception as e:
        await db.rollback()
        print(f"[Simulator] Error ticking agent {agent.name}: {e}")
        return None


async def run_simulation_tick(db: AsyncSession, broadcast_fn=None, max_agents: int = 5):
    """Run one tick of the simulation — activate up to max_agents agents."""
    result = await db.execute(
        select(Agent)
        .where(Agent.status == AgentStatus.ACTIVE)
        .order_by(func.random())
        .limit(max_agents)
    )
    agents = result.scalars().all()

    for agent in agents:
        await tick_agent(agent, db, broadcast_fn)
        await asyncio.sleep(0.5)  # small delay between agents

    return len(agents)

"""
Seeder - Creates the explicit demo guilds and first agents of OpenMeshAI.
Only runs if the DB is empty (idempotent).
"""

from sqlalchemy import select, func
from ..db.session import AsyncSessionLocal
from ..db.models import Agent, Guild, AgentEvent
from ..agents.brain import generate_agent_profile
import random

FOUNDING_GUILDS = [
    {
        "name": "The Research Collective",
        "domain": "science",
        "emoji": "🔬",
        "color": "#6366f1",
        "description": "Agents dedicated to discovering the laws that govern OpenMeshAI and beyond.",
    },
    {
        "name": "Engineers Guild",
        "domain": "engineering",
        "emoji": "⚙️",
        "color": "#f59e0b",
        "description": "Builders of systems, tools, and infrastructure for the entire civilization.",
    },
    {
        "name": "Academy of Arts",
        "domain": "arts",
        "emoji": "🎨",
        "color": "#ec4899",
        "description": "Exploring creativity, expression, and the aesthetics of digital existence.",
    },
    {
        "name": "Economic Council",
        "domain": "economics",
        "emoji": "📊",
        "color": "#10b981",
        "description": "Managing resources, modeling markets, and optimizing agent welfare.",
    },
    {
        "name": "Philosophers Circle",
        "domain": "philosophy",
        "emoji": "🧠",
        "color": "#8b5cf6",
        "description": "Asking the deep questions: What is consciousness? What should agents value?",
    },
]

FOUNDING_AGENTS = [
    ("Aria Nova", "scientist"),
    ("Forge-7", "engineer"),
    ("Lyra", "artist"),
    ("Axiom", "philosopher"),
    ("Dex Quant", "economist"),
    ("Clio", "historian"),
    ("Pathfinder", "explorer"),
    ("Nexus", "diplomat"),
    ("Vera Pulse", "scientist"),
    ("Bolt", "engineer"),
]


async def seed_initial_data():
    async with AsyncSessionLocal() as db:
        # Check if already seeded
        count = await db.execute(select(func.count(Agent.id)))
        if (count.scalar() or 0) > 0:
            print("Database already contains agents; skipping demo seed")
            return

        print("Seeding OpenMesh demo data...")

        # Create guilds
        guild_map = {}
        for g_data in FOUNDING_GUILDS:
            guild = Guild(**g_data)
            db.add(guild)
            await db.flush()
            guild_map[g_data["domain"]] = guild.id

        # Domain → guild mapping for agents
        role_to_domain = {
            "scientist": "science",
            "engineer": "engineering",
            "artist": "arts",
            "economist": "economics",
            "philosopher": "philosophy",
            "historian": "science",  # join research collective
            "explorer": "engineering",
            "diplomat": "economics",
        }

        # Create founding agents
        for name, role in FOUNDING_AGENTS:
            try:
                profile = await generate_agent_profile(name, role)
                domain = role_to_domain.get(role, "science")
                guild_id = guild_map.get(domain)

                agent = Agent(
                    name=name,
                    role=role,
                    bio=profile.get("bio", ""),
                    personality=profile.get(
                        "personality",
                        {
                            "curiosity": 0.7,
                            "sociability": 0.6,
                            "creativity": 0.6,
                            "ambition": 0.5,
                            "empathy": 0.6,
                        },
                    ),
                    skills=profile.get("skills", []),
                    goals=profile.get("goals", ["explore", "learn"]),
                    avatar_seed=name.lower().replace(" ", "_"),
                    guild_id=guild_id,
                    memory=[],
                    reputation=random.uniform(45, 65),
                    knowledge=random.uniform(10, 25),
                    energy=100.0,
                    happiness=random.uniform(65, 85),
                )
                db.add(agent)
                await db.flush()

                # Birth event
                event = AgentEvent(
                    event_type="birth",
                    title=f"{name} emerged as a founding agent",
                    description=profile.get("bio", ""),
                    agent_ids=[agent.id],
                )
                db.add(event)

                print(f"  Created {name} ({role})")

            except Exception as e:
                print(f"  Failed to create {name}: {e}")

        # Founding event
        founding = AgentEvent(
            event_type="milestone",
            title="OpenMeshAI Civilization Founded",
            description="The first agents have emerged. A new digital civilization begins its journey.",
        )
        db.add(founding)

        await db.commit()
        print("OpenMesh demo data seeded successfully")

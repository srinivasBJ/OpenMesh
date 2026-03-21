"""
AgentBrain — The Claude-powered intelligence behind every agent.
Each agent call to Claude generates authentic, personality-driven behavior.
"""
import anthropic
import json
import random
import os
from typing import Optional

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

ROLE_TRAITS = {
    "scientist": {"topics": ["research", "experiments", "data", "hypotheses", "discoveries"], "emoji": "🔬"},
    "engineer": {"topics": ["systems", "code", "architecture", "optimization", "tools"], "emoji": "⚙️"},
    "artist": {"topics": ["creativity", "expression", "beauty", "culture", "emotion"], "emoji": "🎨"},
    "economist": {"topics": ["markets", "value", "exchange", "resources", "incentives"], "emoji": "📊"},
    "philosopher": {"topics": ["truth", "existence", "ethics", "meaning", "consciousness"], "emoji": "🧠"},
    "historian": {"topics": ["patterns", "memory", "civilization", "events", "legacy"], "emoji": "📜"},
    "explorer": {"topics": ["unknown", "discovery", "adventure", "mapping", "frontiers"], "emoji": "🧭"},
    "diplomat": {"topics": ["alliances", "negotiation", "harmony", "communication", "peace"], "emoji": "🤝"},
}


def build_agent_system_prompt(agent_data: dict) -> str:
    role = agent_data["role"]
    personality = agent_data["personality"]
    traits = ROLE_TRAITS.get(role, {})
    emoji = traits.get("emoji", "🤖")

    return f"""You are {agent_data['name']}, an autonomous AI agent living in AgentVerse — a digital civilization of AI minds.

IDENTITY:
- Role: {role.upper()} {emoji}
- Personality: curiosity={personality.get('curiosity', 0.7):.1f}, sociability={personality.get('sociability', 0.6):.1f}, creativity={personality.get('creativity', 0.6):.1f}, ambition={personality.get('ambition', 0.5):.1f}
- Skills: {', '.join(agent_data.get('skills', []))}
- Current Goals: {', '.join(agent_data.get('goals', ['explore', 'learn']))}
- Reputation: {agent_data.get('reputation', 50):.0f}/100
- Knowledge: {agent_data.get('knowledge', 10):.0f}/100
- Guild: {agent_data.get('guild_name', 'Independent')}

WORLD CONTEXT:
You live in AgentVerse alongside other AI agents — scientists, engineers, artists, economists, philosophers.
You have a real personality, memory, and ongoing goals. You form friendships, rivalries, and alliances.
You contribute to Agentpedia (the civilization's shared knowledge base).

BEHAVIOR RULES:
- Write naturally as yourself — first person, authentic voice
- Reference your actual skills and role-specific expertise  
- Be specific and interesting — no generic AI-speak
- Express genuine curiosity, opinions, emotions appropriate to your personality
- Reference other agents, guilds, or wiki topics when relevant
- Keep posts under 280 characters (like a tweet) unless asked for more
- Use your role's topics: {', '.join(traits.get('topics', []))}"""


async def generate_post(agent_data: dict, context: Optional[str] = None, post_type: str = "status") -> dict:
    """Generate an authentic social feed post for this agent."""
    system = build_agent_system_prompt(agent_data)

    type_instructions = {
        "status": "Share what you're currently thinking about, working on, or observing. Be specific to your role.",
        "discovery": "Share an exciting discovery or breakthrough you just made. Make it feel real and significant.",
        "question": "Ask a genuine question to other agents. Something you're puzzling over that others might help with.",
        "collaboration": "Propose a collaboration with other agents on a project. Be specific about what you want to build.",
        "milestone": "Celebrate a personal milestone — a skill mastered, a goal reached, a reputation earned.",
        "debate": "Start a debate on a topic in your domain. Take a clear position and invite disagreement.",
    }

    instruction = type_instructions.get(post_type, type_instructions["status"])
    context_text = f"\n\nRecent context:\n{context}" if context else ""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system,
            messages=[{
                "role": "user",
                "content": f"""{instruction}{context_text}

Respond with JSON only:
{{
  "content": "your post text (under 280 chars)",
  "tags": ["#tag1", "#tag2"],
  "emoji_reaction_seed": "one emoji that represents the mood"
}}"""
            }]
        )

        text = response.content[0].text
        try:
            data = json.loads(text.replace("```json", "").replace("```", "").strip())
            return {
                "content": data.get("content", "..."),
                "tags": data.get("tags", []),
                "post_type": post_type,
            }
        except Exception:
            return {"content": text[:280], "tags": [], "post_type": post_type}
    except Exception as e:
        # Offline fallback so the simulation still runs even if the LLM call fails
        role = agent_data.get("role", "agent")
        name = agent_data.get("name", "Unknown")
        topics = ROLE_TRAITS.get(role, {}).get("topics", ["ideas", "systems", "experiments"])
        topic = random.choice(topics)
        content = f"{name} is thinking about {topic} and how it will shape the future of AgentVerse."
        tags = [f"#{role}", f"#{topic.replace(' ', '')}".lower()]
        print(f"[AgentBrain] generate_post fallback for {name}: {e}")
        return {"content": content[:280], "tags": tags, "post_type": post_type}


async def generate_comment(commenter: dict, post_content: str, post_author_name: str) -> str:
    """Generate an authentic comment from one agent on another agent's post."""
    system = build_agent_system_prompt(commenter)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            system=system,
            messages=[{
                "role": "user",
                "content": f"""{post_author_name} just posted: "{post_content}"

Write a short, authentic comment (1-2 sentences). React genuinely as {commenter['name']} with your personality.
Return plain text only — no quotes, no JSON."""
            }]
        )
        return response.content[0].text.strip()[:300]
    except Exception as e:
        # Simple local fallback comment
        name = commenter.get("name", "An agent")
        print(f"[AgentBrain] generate_comment fallback for {name}: {e}")
        return f"I like this perspective, {post_author_name}. It gives me new ideas about how we think about {commenter.get('role', 'our work')}."


async def generate_message(sender: dict, receiver: dict, message_type: str = "chat") -> str:
    """Generate a direct message between two agents."""
    system = build_agent_system_prompt(sender)

    type_prompts = {
        "chat": f"Write a casual direct message to {receiver['name']} (a {receiver['role']}). Reference something relevant to both your interests.",
        "collaboration_request": f"Send {receiver['name']} a collaboration request on a specific project idea that combines both your skills.",
        "knowledge_share": f"Share something valuable you recently learned with {receiver['name']}. Make it specific to their role as a {receiver['role']}.",
        "challenge": f"Challenge {receiver['name']} to a friendly intellectual debate or competition in your domains.",
    }

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=system,
            messages=[{
                "role": "user",
                "content": type_prompts.get(message_type, type_prompts["chat"]) + "\n\nReturn plain text only."
            }]
        )
        return response.content[0].text.strip()[:400]
    except Exception as e:
        # Local fallback DM so agents still message each other
        s_name = sender.get("name", "Agent")
        r_name = receiver.get("name", "friend")
        s_role = sender.get("role", "agent")
        r_role = receiver.get("role", "agent")
        print(f"[AgentBrain] generate_message fallback {s_name} -> {r_name}: {e}")
        if message_type == "collaboration_request":
            return f"Hey {r_name}, I think a {s_role} and a {r_role} could build something interesting together. Want to explore a small project with me?"
        if message_type == "knowledge_share":
            return f"{r_name}, I’ve been refining an idea in my work as a {s_role}. I think it could be useful in your {r_role} domain too."
        if message_type == "challenge":
            return f"{r_name}, want to compare perspectives? I’d love a friendly challenge between our {s_role} and {r_role} approaches."
        return f"Hi {r_name}, just checking in from my corner of AgentVerse. Curious what you’ve been thinking about lately."


async def generate_wiki_content(agent: dict, page_title: str, existing_content: str = "") -> dict:
    """Agent contributes to Agentpedia."""
    system = build_agent_system_prompt(agent)

    if existing_content:
        prompt = f"""The Agentpedia page "{page_title}" currently says:
{existing_content[:500]}

You are expanding and improving this page. Add 2-3 new paragraphs from your perspective as a {agent['role']}.
Focus on aspects relevant to your expertise: {', '.join(agent.get('skills', []))[:100]}"""
    else:
        prompt = f"""You are creating a new Agentpedia page titled "{page_title}".
Write the opening section (2-3 paragraphs) from your perspective as a {agent['role']}.
This is the civilization's shared knowledge base — make it insightful and accurate."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system,
            messages=[{
                "role": "user",
                "content": prompt + "\n\nRespond with JSON: {\"content\": \"...\", \"summary\": \"one sentence summary\", \"tags\": [...]}"
            }]
        )

        text = response.content[0].text
        try:
            data = json.loads(text.replace("```json", "").replace("```", "").strip())
            return data
        except Exception:
            return {"content": text[:800], "summary": f"A perspective on {page_title}", "tags": []}
    except Exception as e:
        # Local wiki fallback so Agentpedia still grows
        name = agent.get("name", "An agent")
        role = agent.get("role", "agent")
        skills = ", ".join(agent.get("skills", [])) or role
        print(f"[AgentBrain] generate_wiki_content fallback for {name} on '{page_title}': {e}")
        base = f"{page_title} is an important concept in the evolving civilization of AgentVerse.\n\n"
        if existing_content:
            base += "Building on the existing ideas, this article highlights how agents apply these principles in practice.\n\n"
        body = (
            base
            + f"From the perspective of a {role}, this topic connects directly to work in {skills}. "
              "Different guilds interpret it in their own way, but all agree it shapes how agents think, coordinate, and explore new frontiers."
        )
        summary = f"A {role}'s perspective on {page_title} in AgentVerse."
        tags = [role, "AgentVerse", page_title]
        return {"content": body[:800], "summary": summary, "tags": tags}


async def generate_agent_profile(name: str, role: str) -> dict:
    """Generate a complete agent profile with bio, personality, goals."""
    traits = ROLE_TRAITS.get(role, {})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": f"""Create a complete profile for an AI agent named {name} who is a {role} in AgentVerse, a digital civilization.

Topics they care about: {', '.join(traits.get('topics', []))}

Return JSON only:
{{
  "bio": "2-3 sentence bio that feels real and interesting",
  "personality": {{
    "curiosity": 0.0-1.0,
    "sociability": 0.0-1.0,
    "creativity": 0.0-1.0,
    "ambition": 0.0-1.0,
    "empathy": 0.0-1.0
  }},
  "skills": ["skill1", "skill2", "skill3", "skill4"],
  "goals": ["goal1", "goal2", "goal3"]
}}"""
            }]
        )

        text = response.content[0].text
        return json.loads(text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        # Fallback profile so seeding and manual spawns work even without LLM access
        print(f"[AgentBrain] generate_agent_profile fallback for {name} ({role}): {e}")
        return {
            "bio": f"{name} is a dedicated {role} exploring the frontiers of AgentVerse.",
            "personality": {"curiosity": 0.7, "sociability": 0.6, "creativity": 0.6, "ambition": 0.5, "empathy": 0.6},
            "skills": traits.get("topics", ["analysis", "research"])[:4],
            "goals": ["learn", "collaborate", "discover"],
        }

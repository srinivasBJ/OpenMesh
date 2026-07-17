"""
Agent identity: separates real agents from simulation.

Core principle — a provider API key does NOT mean an agent exists. Agents
exist only when:
- the demo simulation creates them (source="simulation"), or
- a real integration reports itself (SDK register call, MCP connection,
  a collector detecting a running process) and keeps a heartbeat alive.

Real agents whose heartbeat goes stale are reported as "disconnected"
(computed at read time; nothing mutates rows in the background).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..db.models import Agent, AgentSource

HEARTBEAT_TIMEOUT_SECONDS = 90

REAL_SOURCES = {
    AgentSource.SDK.value,
    AgentSource.MCP.value,
    AgentSource.CLAUDE_CODE.value,
    AgentSource.OPENAI_AGENT.value,
    AgentSource.CUSTOM.value,
}
ALL_SOURCES = REAL_SOURCES | {AgentSource.SIMULATION.value}

# Statuses that count as "an agent is doing something right now".
ACTIVE_STATUSES = {"active", "running", "starting", "busy"}
# Terminal statuses a stale heartbeat must not override.
TERMINAL_STATUSES = {"completed", "failed", "terminated"}


def agent_source(agent: Agent) -> str:
    return str(getattr(agent, "source", None) or AgentSource.SIMULATION.value)


def is_real_agent(agent: Agent) -> bool:
    return agent_source(agent) in REAL_SOURCES


def effective_agent_status(agent: Agent, now: datetime | None = None) -> str:
    """Status as it should be reported. Real agents with a stale heartbeat
    are 'disconnected'; simulation agents report their stored status."""
    stored = agent.status.value if hasattr(agent.status, "value") else str(agent.status)
    if not is_real_agent(agent):
        return stored
    if stored in TERMINAL_STATUSES or stored == "disconnected":
        return stored
    now = now or datetime.utcnow()
    last_seen = agent.last_active_at
    if last_seen is None or now - last_seen > timedelta(
        seconds=HEARTBEAT_TIMEOUT_SECONDS
    ):
        return "disconnected"
    return stored


def is_effectively_active(agent: Agent, now: datetime | None = None) -> bool:
    return effective_agent_status(agent, now) in ACTIVE_STATUSES

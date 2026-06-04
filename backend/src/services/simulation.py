from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import random
import re
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import (
    Agent,
    AgentEvent,
    AgentRole,
    AgentStatus,
    Guild,
    Message,
    OpenMeshSessionRecord,
    Post,
    PostType,
    WikiContribution,
    WikiPage,
)
from ..shared.openmesh_events import make_openmesh_event
from .openmesh_collector import collector


AGENT_BLUEPRINTS: tuple[tuple[str, AgentRole, list[str]], ...] = (
    ("Research Agent", AgentRole.SCIENTIST, ["search", "summarize", "compare"]),
    ("Planner Agent", AgentRole.PHILOSOPHER, ["plan", "sequence", "scope"]),
    ("Reviewer Agent", AgentRole.HISTORIAN, ["review", "audit", "trace"]),
    ("Coding Agent", AgentRole.ENGINEER, ["python", "git", "tests"]),
    ("Scientist Agent", AgentRole.SCIENTIST, ["experiments", "hypothesis"]),
    ("Explorer Agent", AgentRole.EXPLORER, ["discovery", "mapping"]),
    ("Memory Agent", AgentRole.HISTORIAN, ["recall", "indexing"]),
    ("Toolsmith Agent", AgentRole.ENGINEER, ["tools", "adapters"]),
    ("Synthesis Agent", AgentRole.DIPLOMAT, ["synthesis", "handoffs"]),
    ("Data Agent", AgentRole.ECONOMIST, ["metrics", "datasets"]),
    ("Safety Agent", AgentRole.DIPLOMAT, ["policy", "review"]),
    ("Ops Agent", AgentRole.ENGINEER, ["runtime", "observability"]),
    ("Catalog Agent", AgentRole.HISTORIAN, ["wiki", "taxonomy"]),
    ("Debate Agent", AgentRole.PHILOSOPHER, ["critique", "questions"]),
    ("Design Agent", AgentRole.ARTIST, ["ux", "systems"]),
    ("Field Agent", AgentRole.EXPLORER, ["collection", "notes"]),
    ("Protocol Agent", AgentRole.ENGINEER, ["schemas", "events"]),
    ("Navigator Agent", AgentRole.EXPLORER, ["routes", "graph"]),
    ("Archivist Agent", AgentRole.HISTORIAN, ["records", "lineage"]),
    ("Coordinator Agent", AgentRole.DIPLOMAT, ["coordination", "handoffs"]),
)

GUILD_BLUEPRINTS: tuple[tuple[str, str, str, str], ...] = (
    ("Research Guild", "research", "[R]", "#bd5c2b"),
    ("Runtime Guild", "engineering", "[E]", "#9f4a24"),
    ("Knowledge Guild", "knowledge", "[K]", "#c47a35"),
    ("Operations Guild", "operations", "[O]", "#7f3b1f"),
)

TOOL_BLUEPRINTS: tuple[tuple[str, list[str]], ...] = (
    ("web_search", ["search", "source ranking", "summaries"]),
    ("file_reader", ["local files", "artifact reading"]),
    ("python_executor", ["python", "notebooks", "experiments"]),
    ("github_tool", ["issues", "pull requests", "commits"]),
    ("document_store", ["retrieval", "notes", "wiki"]),
    ("trace_viewer", ["trace reconstruction", "span inspection"]),
)

WORKFLOW_NAMES: tuple[str, ...] = (
    "Research Intake",
    "Planning Loop",
    "Implementation Pass",
    "Evidence Review",
    "Knowledge Publish",
    "Operations Sweep",
)

MESSAGE_TEMPLATES: tuple[str, ...] = (
    "handoff ready: evidence packet attached",
    "please review tool output before synthesis",
    "workflow branch selected after trace review",
    "relationship evidence updated in graph",
    "wiki draft ready for guild review",
)

WIKI_TOPICS: tuple[tuple[str, str], ...] = (
    ("Agent Network Map", "How observed agents, tools, and workflows connect."),
    ("Trace Replay Notes", "A walkthrough of replaying workflow execution history."),
    ("Tool Evidence Ledger", "A record of tool usage and provenance evidence."),
    ("Guild Operating Manual", "Shared practices for coordinating agent guilds."),
    ("Simulation Field Report", "Synthetic ecosystem observations for demos."),
)

DISTRIBUTED_NODE_BLUEPRINTS: tuple[tuple[str, str], ...] = (
    ("laptop", "Field Laptop"),
    ("workstation", "Control Workstation"),
    ("server", "Rack Server"),
    ("cloud", "Cloud Relay"),
)

MCP_SERVER_BLUEPRINTS: tuple[tuple[str, str], ...] = (
    ("filesystem-server", "stdio"),
    ("github-server", "http"),
    ("memory-server", "stdio"),
    ("postgres-server", "tcp"),
)


@dataclass
class SimulationTrace:
    trace_id: str
    workflow_node: dict[str, Any]
    lead_agent: dict[str, Any]
    workflow_span_id: str
    root_event_id: str | None = None
    last_event_id: str | None = None
    completed: bool = False


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def _agent_graph_node(
    run_id: str, index: int, name: str, role: AgentRole
) -> dict[str, Any]:
    return {
        "node_id": f"agent:sim:{run_id}:{index:02d}",
        "node_type": "agent",
        "name": name,
        "runtime": "openmesh.simulator",
        "metadata": {"role": role.value},
    }


def _tool_graph_node(name: str) -> dict[str, Any]:
    capabilities = dict(TOOL_BLUEPRINTS)[name]
    return {
        "node_id": f"tool:{name}",
        "node_type": "tool",
        "name": name,
        "runtime": "local.simulation",
        "metadata": {"capabilities": capabilities},
    }


def _workflow_graph_node(run_id: str, index: int, name: str) -> dict[str, Any]:
    return {
        "node_id": f"workflow:sim:{run_id}:{index:02d}",
        "node_type": "workflow",
        "name": name,
        "runtime": "openmesh.simulator",
        "metadata": {
            "framework": "openmesh-sim",
            "source": "openmesh simulate",
            "version": "0.2",
        },
    }


def _file_graph_node(run_id: str, title: str) -> dict[str, Any]:
    slug = _slug(title)
    return {
        "node_id": f"file:sim:{run_id}:{slug}.md",
        "node_type": "file",
        "name": f"{title}.md",
        "runtime": "local.file",
        "metadata": {"path": f"wiki/{slug}.md"},
    }


def _distributed_graph_node(
    run_id: str, index: int, kind: str, name: str
) -> dict[str, Any]:
    node_name = f"{name} {run_id}"
    return {
        "node_id": f"openmesh-node:sim:{run_id}:{kind}:{index:02d}",
        "node_type": "openmesh_node",
        "name": node_name,
        "runtime": "openmesh.simulator",
        "metadata": {
            "node_type": kind,
            "node_kind": kind,
            "hostname": f"{_slug(name)}-{run_id}",
            "platform": "simulation",
            "status": "active",
        },
    }


def _runtime_graph_node(run_id: str, index: int, host_kind: str) -> dict[str, Any]:
    executable = {
        "laptop": "codex",
        "workstation": "claude",
        "server": "opencode",
        "cloud": "openmesh-worker",
    }.get(host_kind, "openmesh-worker")
    return {
        "node_id": f"runtime:sim:{run_id}:{host_kind}:{index:02d}",
        "node_type": "runtime",
        "name": f"{host_kind.title()} Runtime",
        "runtime": "openmesh.simulator",
        "metadata": {
            "executable": executable,
            "status": "active",
            "detected": True,
        },
    }


def _mcp_graph_node(
    run_id: str, index: int, name: str, transport: str
) -> dict[str, Any]:
    return {
        "node_id": f"mcp:sim:{run_id}:{_slug(name)}:{index:02d}",
        "node_type": "mcp_server",
        "name": name,
        "runtime": "openmesh.simulator",
        "metadata": {
            "transport": transport,
            "endpoint": f"simulation://{_slug(name)}",
            "version": "sim-0.2",
        },
    }


async def run_local_simulation(
    db: AsyncSession,
    *,
    agent_count: int = 14,
    event_count: int = 300,
    node_count: int = 0,
    seed: int | None = None,
    broadcast: bool = False,
) -> dict[str, Any]:
    if agent_count < 2:
        raise ValueError("--agents must be at least 2")
    if node_count < 0:
        raise ValueError("--nodes must be greater than or equal to 0")
    minimum_events = agent_count + node_count
    if event_count < minimum_events:
        raise ValueError("--events must be greater than or equal to --agents + --nodes")

    rng = random.Random(seed)
    run_id = uuid4().hex[:8]
    session_id = f"sess_sim_{run_id}"
    started_at = datetime.utcnow()
    command = f"openmesh simulate --agents {agent_count} --events {event_count}"
    if node_count:
        command = f"{command} --nodes {node_count}"
    if seed is not None:
        command = f"{command} --seed {seed}"

    session_record = OpenMeshSessionRecord(
        session_id=session_id,
        command=command,
        started_at=started_at,
        status="running",
    )
    db.add(session_record)

    guilds = _create_guilds(run_id)
    for guild in guilds:
        db.add(guild)

    agents, agent_nodes = _create_agents(run_id, agent_count, rng, guilds)
    for agent in agents:
        db.add(agent)

    wiki_pages, wiki_nodes = _create_wiki_pages(run_id, guilds)
    for page in wiki_pages:
        db.add(page)

    await db.flush()

    for contribution in _create_wiki_contributions(agents, wiki_pages):
        db.add(contribution)
    posts = _create_posts(agents, wiki_pages, rng, event_count)
    messages = _create_messages(agents, rng, event_count)
    legacy_events = _create_legacy_timeline_events(run_id, agents, guilds)
    for record in [*posts, *messages, *legacy_events]:
        db.add(record)
    await db.commit()

    emitted: list[dict[str, Any]] = []
    tool_calls = 0
    host_relationships = 0
    traces = _create_trace_contexts(run_id, agent_nodes, rng, event_count)
    tool_nodes = [_tool_graph_node(name) for name, _ in TOOL_BLUEPRINTS]
    distributed_nodes = _create_distributed_nodes(run_id, node_count)
    runtime_nodes = _create_runtime_nodes(run_id, distributed_nodes)
    mcp_nodes = _create_mcp_nodes(run_id, distributed_nodes)

    async def emit(
        event_type: str,
        source: dict[str, Any],
        payload: dict[str, Any],
        *,
        target: dict[str, Any] | None = None,
        trace: SimulationTrace | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        parent_event_id: str | None = None,
        root_event_id: str | None = None,
        links: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if len(emitted) >= event_count:
            return None
        if trace:
            trace_id = trace.trace_id
            span_id = span_id or trace.workflow_span_id
            parent_event_id = parent_event_id or trace.last_event_id
            root_event_id = root_event_id or trace.root_event_id
        else:
            trace_id = f"trace_sim_{run_id}_registry"
            span_id = span_id or f"span_sim_{run_id}_registry"
        event = make_openmesh_event(
            event_type,
            source,
            payload,
            target=target,
            session_id=session_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            parent_event_id=parent_event_id,
            root_event_id=root_event_id,
            links=links,
        )
        await collector.accept(db, event, broadcast=broadcast)
        emitted.append(event)
        if trace:
            trace.root_event_id = trace.root_event_id or event["root_event_id"]
            trace.last_event_id = event["event_id"]
        return event

    for node in distributed_nodes:
        await emit(
            "node.joined",
            node,
            {
                "simulation_run_id": run_id,
                "node_id": node["node_id"],
                "node_name": node["name"],
                "node_type": node["metadata"]["node_type"],
                "status": "active",
            },
        )

    for node in agent_nodes:
        await emit(
            "agent.registered",
            node,
            {
                "simulation_run_id": run_id,
                "status": "active",
                "role": node["metadata"]["role"],
            },
        )

    if distributed_nodes:
        for index, target in enumerate(agent_nodes):
            event = await emit(
                "node.heartbeat",
                distributed_nodes[index % len(distributed_nodes)],
                {
                    "simulation_run_id": run_id,
                    "relationship_type": "hosts",
                    "hosted_type": "agent",
                    "status": "active",
                },
                target=target,
            )
            host_relationships += 1 if event else 0
        for index, target in enumerate(runtime_nodes):
            event = await emit(
                "node.heartbeat",
                distributed_nodes[index % len(distributed_nodes)],
                {
                    "simulation_run_id": run_id,
                    "relationship_type": "hosts",
                    "hosted_type": "runtime",
                    "status": "active",
                },
                target=target,
            )
            host_relationships += 1 if event else 0
        for index, target in enumerate(mcp_nodes):
            event = await emit(
                "node.heartbeat",
                distributed_nodes[index % len(distributed_nodes)],
                {
                    "simulation_run_id": run_id,
                    "relationship_type": "hosts",
                    "hosted_type": "mcp_server",
                    "status": "active",
                },
                target=target,
            )
            host_relationships += 1 if event else 0

    for trace in traces:
        await emit(
            "workflow.started",
            trace.lead_agent,
            {
                "workflow_id": trace.workflow_node["node_id"],
                "workflow": trace.workflow_node["name"],
                "simulation_run_id": run_id,
            },
            target=trace.workflow_node,
            trace=trace,
            span_id=trace.workflow_span_id,
        )

    if agent_nodes and traces and wiki_nodes:
        first_trace = traces[0]
        first_agent = agent_nodes[0]
        second_agent = agent_nodes[1]
        await emit(
            "message.sent",
            first_agent,
            {
                "message": "simulation channel established",
                "channel": "simulation",
                "simulation_run_id": run_id,
            },
            target=second_agent,
            trace=first_trace,
        )
        await emit(
            "collaboration.created",
            first_agent,
            {
                "title": "initial graph collaboration",
                "relationship": "collaborates_with",
                "simulation_run_id": run_id,
            },
            target=second_agent,
            trace=first_trace,
        )
        await emit(
            "delegation.created",
            first_agent,
            {
                "task": "seed planner handoff",
                "simulation_run_id": run_id,
            },
            target=second_agent,
            trace=first_trace,
        )
        if len(traces) > 1:
            await emit(
                "node.transition",
                first_trace.workflow_node,
                {
                    "from": first_trace.workflow_node["name"],
                    "to": traces[1].workflow_node["name"],
                    "simulation_run_id": run_id,
                },
                target=traces[1].workflow_node,
                trace=first_trace,
            )
        await emit(
            "file.modified",
            first_agent,
            {
                "operation": "wiki.seed",
                "simulation_run_id": run_id,
            },
            target=wiki_nodes[0],
            trace=first_trace,
        )

    desired_tool_calls = min(max(1, event_count // 5), 100, event_count // 3)
    while len(emitted) < event_count:
        trace = rng.choice(traces)
        remaining = event_count - len(emitted)
        if tool_calls < desired_tool_calls and remaining >= 2:
            start_event = await _emit_tool_call(
                emit,
                trace,
                rng.choice(agent_nodes),
                rng.choice(tool_nodes),
                tool_calls,
                run_id,
            )
            if start_event:
                tool_calls += 1
            continue
        if remaining >= 2 and not trace.completed and rng.random() < 0.15:
            await emit(
                "workflow.completed",
                trace.lead_agent,
                {
                    "workflow_id": trace.workflow_node["node_id"],
                    "status": "completed",
                    "simulation_run_id": run_id,
                },
                target=trace.workflow_node,
                trace=trace,
                span_id=trace.workflow_span_id,
            )
            trace.completed = True
            continue

        choice = rng.choice(
            (
                "message",
                "collaboration",
                "delegation",
                "transition",
                "wiki",
                "task",
            )
        )
        if choice == "message":
            source, target = rng.sample(agent_nodes, 2)
            await emit(
                "message.sent",
                source,
                {
                    "message": rng.choice(MESSAGE_TEMPLATES),
                    "channel": "simulation",
                    "simulation_run_id": run_id,
                },
                target=target,
                trace=trace,
            )
        elif choice == "collaboration":
            source, target = rng.sample(agent_nodes, 2)
            await emit(
                "collaboration.created",
                source,
                {
                    "title": "shared evidence review",
                    "relationship": "collaborates_with",
                    "simulation_run_id": run_id,
                },
                target=target,
                trace=trace,
            )
        elif choice == "delegation":
            source, target = rng.sample(agent_nodes, 2)
            await emit(
                "delegation.created",
                source,
                {
                    "task": "prepare next workflow step",
                    "simulation_run_id": run_id,
                },
                target=target,
                trace=trace,
            )
        elif choice == "transition":
            source_trace, target_trace = rng.sample(traces, 2)
            await emit(
                "node.transition",
                source_trace.workflow_node,
                {
                    "from": source_trace.workflow_node["name"],
                    "to": target_trace.workflow_node["name"],
                    "simulation_run_id": run_id,
                },
                target=target_trace.workflow_node,
                trace=trace,
            )
        elif choice == "wiki":
            await emit(
                "file.modified",
                rng.choice(agent_nodes),
                {
                    "operation": "wiki.update",
                    "simulation_run_id": run_id,
                },
                target=rng.choice(wiki_nodes),
                trace=trace,
            )
        else:
            await emit(
                rng.choice(("task.started", "task.completed")),
                rng.choice(agent_nodes),
                {
                    "task": "advance simulated ecosystem workflow",
                    "simulation_run_id": run_id,
                },
                target=trace.workflow_node,
                trace=trace,
            )

    ended_at = datetime.utcnow()
    session_record.ended_at = ended_at
    session_record.status = "completed"
    session_record.exit_code = 0
    db.add(session_record)
    await db.commit()

    return {
        "run_id": run_id,
        "session_id": session_id,
        "agents": len(agents),
        "guilds": len(guilds),
        "events": len(emitted),
        "tool_calls": tool_calls,
        "workflows": len(traces),
        "distributed_nodes": len(distributed_nodes),
        "host_relationships": host_relationships,
        "runtimes": len(runtime_nodes),
        "mcp_servers": len(mcp_nodes),
        "messages": len(messages),
        "posts": len(posts),
        "wiki_articles": len(wiki_pages),
        "traces": len({event["trace_id"] for event in emitted}),
        "trace_ids": sorted({event["trace_id"] for event in emitted}),
        "started_at": started_at.isoformat() + "Z",
        "ended_at": ended_at.isoformat() + "Z",
    }


async def _emit_tool_call(
    emit,
    trace: SimulationTrace,
    agent: dict[str, Any],
    tool: dict[str, Any],
    index: int,
    run_id: str,
) -> dict[str, Any] | None:
    call_id = f"tool_sim_{run_id}_{index:04d}"
    span_id = f"span_sim_{run_id}_tool_{index:04d}"
    start_event = await emit(
        "tool.call.started",
        agent,
        {
            "tool": tool["name"],
            "call_id": call_id,
            "input": {"query": f"simulation evidence request {index}"},
            "simulation_run_id": run_id,
        },
        target=tool,
        trace=trace,
        span_id=span_id,
        parent_span_id=trace.workflow_span_id,
    )
    if not start_event:
        return None
    await emit(
        "tool.call.completed",
        agent,
        {
            "tool": tool["name"],
            "call_id": call_id,
            "status": "completed",
            "output_preview": "synthetic evidence captured",
            "simulation_run_id": run_id,
        },
        target=tool,
        trace=trace,
        span_id=span_id,
        parent_span_id=trace.workflow_span_id,
        parent_event_id=start_event["event_id"],
        root_event_id=trace.root_event_id,
        links=[{"event_id": start_event["event_id"], "type": "follows"}],
    )
    return start_event


def _create_distributed_nodes(run_id: str, node_count: int) -> list[dict[str, Any]]:
    nodes = []
    for index in range(node_count):
        kind, name = DISTRIBUTED_NODE_BLUEPRINTS[
            index % len(DISTRIBUTED_NODE_BLUEPRINTS)
        ]
        nodes.append(_distributed_graph_node(run_id, index + 1, kind, name))
    return nodes


def _create_runtime_nodes(
    run_id: str, distributed_nodes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        _runtime_graph_node(run_id, index + 1, node["metadata"]["node_type"])
        for index, node in enumerate(distributed_nodes)
    ]


def _create_mcp_nodes(
    run_id: str, distributed_nodes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not distributed_nodes:
        return []
    count = min(len(distributed_nodes), len(MCP_SERVER_BLUEPRINTS))
    return [
        _mcp_graph_node(run_id, index + 1, name, transport)
        for index, (name, transport) in enumerate(MCP_SERVER_BLUEPRINTS[:count])
    ]


def _create_guilds(run_id: str) -> list[Guild]:
    guilds = []
    for name, domain, emblem, color in GUILD_BLUEPRINTS:
        guilds.append(
            Guild(
                name=f"{name} {run_id}",
                description=f"Simulation guild for {domain} activity.",
                domain=domain,
                emoji=emblem,
                color=color,
                reputation=65.0,
            )
        )
    return guilds


def _create_agents(
    run_id: str,
    agent_count: int,
    rng: random.Random,
    guilds: list[Guild],
) -> tuple[list[Agent], list[dict[str, Any]]]:
    agents = []
    nodes = []
    for index in range(agent_count):
        base_name, role, skills = AGENT_BLUEPRINTS[index % len(AGENT_BLUEPRINTS)]
        name = f"{base_name} {run_id}-{index + 1:02d}"
        guild = guilds[index % len(guilds)]
        agent = Agent(
            name=name,
            role=role,
            status=rng.choice((AgentStatus.ACTIVE, AgentStatus.BUSY, AgentStatus.IDLE)),
            personality={"style": "simulation", "focus": role.value},
            skills=skills,
            bio=f"Local simulated {base_name.lower()} for OpenMesh demos.",
            avatar_seed=f"sim-{run_id}-{index}",
            reputation=round(rng.uniform(45, 95), 2),
            knowledge=round(rng.uniform(20, 90), 2),
            energy=round(rng.uniform(50, 100), 2),
            happiness=round(rng.uniform(55, 95), 2),
            memory=[],
            goals=["map relationships", "publish traceable results"],
            guild=guild,
            total_posts=0,
            total_collaborations=0,
        )
        agents.append(agent)
        nodes.append(_agent_graph_node(run_id, index + 1, name, role))
    return agents, nodes


def _create_wiki_pages(
    run_id: str, guilds: list[Guild]
) -> tuple[list[WikiPage], list[dict[str, Any]]]:
    pages = []
    nodes = []
    for index, (title, summary) in enumerate(WIKI_TOPICS):
        name = f"{title} {run_id}"
        slug = f"sim-{run_id}-{_slug(title)}"
        pages.append(
            WikiPage(
                slug=slug,
                title=name,
                content=f"# {name}\n\n{summary}\n\nGenerated by openmesh simulate.",
                summary=summary,
                category="simulation",
                tags=["simulation", "openmesh", "graph"],
                primary_guild=guilds[index % len(guilds)],
                quality_score=72.0 + index,
            )
        )
        nodes.append(_file_graph_node(run_id, title))
    return pages, nodes


def _create_wiki_contributions(
    agents: list[Agent], pages: list[WikiPage]
) -> list[WikiContribution]:
    if not agents:
        return []
    contributions = []
    for index, page in enumerate(pages):
        contributions.append(
            WikiContribution(
                page=page,
                agent=agents[index % len(agents)],
                content_added=page.summary or "simulation note",
                contribution_type="simulation",
            )
        )
    return contributions


def _create_posts(
    agents: list[Agent],
    wiki_pages: list[WikiPage],
    rng: random.Random,
    event_count: int,
) -> list[Post]:
    count = min(max(6, event_count // 20), 30)
    posts = []
    for index in range(count):
        agent = agents[index % len(agents)]
        wiki = rng.choice(wiki_pages)
        post_type = rng.choice(
            (
                PostType.STATUS,
                PostType.DISCOVERY,
                PostType.COLLABORATION,
                PostType.MILESTONE,
            )
        )
        posts.append(
            Post(
                author=agent,
                content=f"{agent.name} recorded {post_type.value} evidence for {wiki.title}.",
                post_type=post_type,
                tags=["simulation", "openmesh", wiki.category or "wiki"],
                mentions=[],
                linked_wiki=wiki.slug,
                reactions={"ack": rng.randint(0, 6), "useful": rng.randint(0, 4)},
            )
        )
        agent.total_posts = (agent.total_posts or 0) + 1
    return posts


def _create_messages(
    agents: list[Agent], rng: random.Random, event_count: int
) -> list[Message]:
    count = min(max(10, event_count // 10), 80)
    messages = []
    for _ in range(count):
        sender, receiver = rng.sample(agents, 2)
        messages.append(
            Message(
                sender=sender,
                receiver=receiver,
                content=rng.choice(MESSAGE_TEMPLATES),
                message_type="simulation",
            )
        )
        sender.total_collaborations = (sender.total_collaborations or 0) + 1
    return messages


def _create_legacy_timeline_events(
    run_id: str, agents: list[Agent], guilds: list[Guild]
) -> list[AgentEvent]:
    return [
        AgentEvent(
            event_type="simulation.started",
            title="OpenMesh simulation started",
            description="Local synthetic ecosystem data was generated.",
            agent_ids=[agent.name for agent in agents[:6]],
            guild_id=guilds[0].name if guilds else None,
            data={"simulation_run_id": run_id},
        ),
        AgentEvent(
            event_type="simulation.workflow_milestone",
            title="Synthetic workflows populated",
            description="Generated agents, tools, workflows, messages, and wiki artifacts.",
            agent_ids=[agent.name for agent in agents[6:12]],
            guild_id=guilds[1].name if len(guilds) > 1 else None,
            data={"simulation_run_id": run_id},
        ),
    ]


def _create_trace_contexts(
    run_id: str,
    agent_nodes: list[dict[str, Any]],
    rng: random.Random,
    event_count: int,
) -> list[SimulationTrace]:
    workflow_count = min(max(3, event_count // 100 + 2), len(WORKFLOW_NAMES))
    traces = []
    for index in range(workflow_count):
        workflow = _workflow_graph_node(run_id, index + 1, WORKFLOW_NAMES[index])
        traces.append(
            SimulationTrace(
                trace_id=f"trace_sim_{run_id}_{index + 1:02d}",
                workflow_node=workflow,
                lead_agent=rng.choice(agent_nodes),
                workflow_span_id=f"span_sim_{run_id}_workflow_{index + 1:02d}",
            )
        )
    return traces

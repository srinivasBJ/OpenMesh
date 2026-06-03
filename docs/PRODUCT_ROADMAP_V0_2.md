# OpenMesh Product Roadmap v0.2

Date: 2026-06-03

Scope: product planning for OpenMesh v0.2. This document does not implement
features, change architecture, add integrations, add protocols, or modify
source behavior.

## Executive Summary

OpenMesh v0.1-alpha proves the architecture works. Installation, onboarding,
CLI commands, TUI rendering, graph reduction, discovery, ecosystem inventory,
timeline, replay, diagnostics, Python SDK, and LangGraph integration have all
been validated.

OpenMesh v0.2 should not primarily add more backend machinery. It should make
the existing graph, trace, timeline, and replay capabilities feel like one
coherent product.

The v0.2 theme:

```text
From observable data to navigable agent networks.
```

## 1. Current Maturity Score

Overall maturity score: 7.0 / 10

Breakdown:

| Area | Score | Notes |
| --- | ---: | --- |
| Core architecture | 8.5 | Event -> trace -> graph -> discovery -> timeline -> replay flow is coherent and validated. |
| Installation | 8.0 | Fresh SQLite install now works; Python 3.11-3.13 requirement is clear. |
| CLI | 7.5 | Broad command coverage; output is useful but not yet strongly guided. |
| TUI | 6.5 | Strong identity and layout foundation; interaction model needs graph-first focus. |
| Graph experience | 6.0 | Accurate relationship/provenance output, but not yet exploratory. |
| SDK and integrations | 7.0 | Python SDK and LangGraph path validate the model; ecosystem coverage still early. |
| Documentation | 7.0 | Startup docs are stronger; root product story still contains legacy OpenMeshAI/simulator framing. |
| Daily usability | 5.5 | Users can inspect data, but repeat workflows need fewer manual pivots and better context preservation. |

Interpretation:

OpenMesh v0.1-alpha is a credible technical alpha. OpenMesh v0.2 should become
a credible user alpha.

## 2. Adoption Blockers

### Product Identity Is Still Split

The current docs still carry two stories:

- OpenMesh as terminal-first observability for agent ecosystems.
- OpenMeshAI as an older simulator/dashboard/civilization prototype.

The architecture can support both, but public adoption needs one lead story.

v0.2 direction:

OpenMesh is agent ecosystem observability. The simulator and browser dashboard
are demonstrations and compatibility layers, not the product center.

### Optional Integrations Need Clear Expectations

`openmesh integrations` correctly reports optional frameworks as installed or
not installed. New users may still interpret `Not installed` as a broken
OpenMesh install.

v0.2 direction:

Make integration states explicit:

- built in
- plugin available
- framework package missing
- configured
- observed activity

### Examples Need A Guided Path

The validated example path works, but users still need to know which examples
are core, optional, metadata-only, or framework-dependent.

v0.2 direction:

Create a guided `First 10 Minutes` path:

```text
run process example
run Python SDK example
run LangGraph example
open TUI
inspect graph
replay workflow
```

### Packaging Is Installable But Not Yet Polished

OpenMesh installs from source and has release hardening docs. The next adoption
step is removing friction around package install, version support, and common
environment issues.

v0.2 direction:

Make installation feel boring:

- exact Python support
- package install smoke tests
- clean TestPyPI/PyPI instructions
- clearer Postgres vs SQLite guidance
- startup diagnostics with direct next commands

### Repository Hygiene Still Signals Prototype

The installation audit found local duplicate `* 2.py` and `* 2.sql` files,
legacy naming, old dashboard language, and draft artifacts.

v0.2 direction:

Do a product-facing cleanup pass before wider user outreach.

## 3. UX Blockers

### The Graph Is Correct But Static

Current graph output explains relationships, but it behaves like a report. Users
must manually decide where to go next.

v0.2 goal:

Make the graph navigable:

```text
select node -> inspect -> expand -> trace -> replay -> return to graph
```

### Inspect Requires Prior Node Knowledge

`openmesh inspect <node_id>` is powerful, but users need to discover and copy
ids first.

v0.2 goal:

Let users inspect from selection, search, or suggested next commands.

### Timeline And Replay Are Conceptually Strong But Dense

Timeline and replay prove historical reconstruction, but current output is
still event-heavy.

v0.2 goal:

Show evolution as graph changes:

- node appeared
- relationship created
- workflow started
- workflow transitioned
- trace completed
- snapshot changed

### TUI Has Modes But Needs A Single Mental Model

The TUI already has panels, graph filters, discovery, snapshots, timeline,
replay, query, and inspection. The missing layer is focus.

v0.2 goal:

The selected entity should drive every panel.

### Discovery And Ecosystem Views Overlap

Both views are valuable, but users need simpler language.

v0.2 goal:

- Discovery = Observed activity.
- Ecosystem = Governed inventory.

## 4. Ecosystem Blockers

### Framework Coverage Is Early

LangGraph is validated. Other plugins exist, but real-world confidence depends
on framework-specific callback coverage and user feedback.

v0.2 direction:

Do not rush more integrations until the graph exploration UX is strong. A small
number of excellent integration journeys is better than a long list of shallow
ones.

### Plugin Story Needs Product Framing

The plugin architecture exists, but users need to understand the practical
workflow:

```text
openmesh plugins list
openmesh integrations
install framework package
run example
see graph
```

### MCP Is Metadata-Only And Should Stay Honest

MCP registry/config/capability support is intentionally metadata-only. Users
should not infer that OpenMesh executes MCP tools, performs health checks, or
does security analysis.

v0.2 direction:

Keep MCP wording precise:

- discovers configuration metadata
- registers servers and declared capabilities
- maps relationships
- does not call tools
- does not inspect credentials

## 5. Product Positioning

### One Sentence

OpenMesh is a terminal-first observability layer for AI agent ecosystems that
turns events, traces, tools, workflows, processes, and integrations into a
navigable relationship graph.

### One Paragraph

OpenMesh helps AI engineers and agent platform teams understand what their
agent systems are doing. Instead of treating agent activity as disconnected
logs, OpenMesh collects structured events from CLIs, SDKs, processes, and
framework integrations, reconstructs traces and workflows, derives a governed
ecosystem graph, and exposes that graph through CLI, TUI, API, and optional
dashboard views. The core product is the living map of agents, tools,
workflows, services, MCP metadata, capabilities, processes, traces, sessions,
and the relationships between them.

### One Page

Agent systems are becoming networks. A single result can involve a coding
agent, a research agent, a workflow runtime, a browser tool, a local process,
MCP servers, framework callbacks, memory systems, and provider calls. Most
tools make this activity visible only as logs or isolated traces. Logs are
useful, but they do not explain the shape of the system.

OpenMesh exists to show the shape.

OpenMesh collects structured events from agent runtimes, SDKs, process
observation, and framework integrations. Those events become traces, spans,
sessions, workflows, graph nodes, graph relationships, discovery registries,
ecosystem inventory, timelines, replays, snapshots, and diagnostics. The graph
is not decorative. It is the main product object.

The ideal OpenMesh user can start from a terminal, run an agent or workflow,
open `openmesh tui`, and immediately see which entities exist, how they are
connected, which trace created each edge, which workflow ran, which tool was
used, and how the network changed over time. They can inspect an entity,
follow relationships, replay a trace, compare snapshots, and return to the
network without losing context.

OpenMesh is not a replacement for agent frameworks. It is the observability and
relationship layer around them. LangGraph, CrewAI, AutoGen, OpenHands, Claude
Code, OpenCode, custom agents, and future runtimes should be able to emit
OpenMesh events and appear in the same ecosystem map.

OpenMesh is also not a security analyzer or root-cause engine in v0.2. Those
may become future layers. First, the product must make discovery, registry,
relationship mapping, trace reconstruction, provenance, and replay dependable
and understandable.

The v0.2 product promise:

```text
Run agents. See the network. Follow the evidence.
```

## 6. Target Users

### AI Engineers

Need to observe local agent runs, tool calls, traces, workflows, and failures
without standing up a heavyweight dashboard.

Primary value:

- understand what happened
- debug workflow behavior
- inspect tool and process usage
- replay execution

### Agent Developers

Need a simple SDK and terminal feedback loop while building custom agents.

Primary value:

- emit events easily
- validate traces
- inspect relationships created by their agent
- understand tool usage and message flow

### Framework Authors

Need a standard way to expose framework execution semantics without building a
custom observability UI.

Primary value:

- map nodes, tasks, tools, workflows, transitions, and runtime metadata
- provide users with OpenMesh-compatible instrumentation
- validate plugin behavior through common diagnostics

### Observability Engineers

Need agent-specific telemetry that complements logs, metrics, and traces.

Primary value:

- relationship provenance
- trace/span semantics
- graph-derived topology
- historical timeline and snapshot diffing

### Platform Teams

Need to understand agent ecosystems across repositories, runtimes, tools, and
teams.

Primary value:

- inventory of observed agents, tools, workflows, MCP metadata, and services
- integration registry
- federation-ready metadata direction
- daily control-room view

### Researchers

Need to study multi-agent systems, workflow behavior, and ecosystem evolution.

Primary value:

- replayable traces
- graph snapshots
- timeline data
- structured queries over observed behavior

## 7. Ideal User Journey

### Step 1 - First Install

User goal:

Install OpenMesh locally without Docker or prior knowledge.

Ideal flow:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
openmesh doctor
```

Success state:

The user sees `Overall: OK` and a next action.

### Step 2 - Run First Example

User goal:

Create observable data immediately.

Ideal flow:

```bash
openmesh run -- python -c "print('hello openmesh')"
python examples/python_basic_agent.py
```

Success state:

OpenMesh shows a process, service, agent, tool, trace, and relationship.

### Step 3 - Observe Agent Activity

User goal:

See what OpenMesh observed.

Ideal flow:

```bash
openmesh discover
openmesh ecosystem
openmesh events
openmesh traces
```

Success state:

The user understands the inventory:

- agents
- tools
- processes
- services
- workflows
- integrations

### Step 4 - Explore Graph

User goal:

Move from inventory to relationships.

Ideal flow:

```bash
openmesh graph --details
openmesh tui
```

v0.2 target:

The TUI graph panel supports selection, search, expansion, filters, and
relationship inspection.

### Step 5 - Inspect Entity

User goal:

Answer "what is this and why is it connected?"

Ideal flow:

```bash
openmesh inspect research-agent
```

v0.2 target:

Inspection shows:

- identity
- status
- first/last seen
- incoming relationships
- outgoing relationships
- traces
- sessions
- provenance summary
- next actions

### Step 6 - Replay Workflow

User goal:

Understand how a workflow or trace formed the graph.

Ideal flow:

```bash
python -m pip install langgraph
python examples/langgraph_basic.py
openmesh replay workflow "workflow:LangGraph Basic"
```

v0.2 target:

Replay highlights:

- workflow start
- node transitions
- span tree
- graph edges created
- trace evidence

### Step 7 - Integrate Own Framework

User goal:

Use OpenMesh without modifying collector internals.

Ideal flow:

```python
from openmesh import OpenMeshClient

client = OpenMeshClient()
agent = client.agent(id="research-agent", name="Research Agent")

with agent.task("Research"):
    with agent.tool("web_search"):
        ...
```

v0.2 target:

Documentation maps custom frameworks to:

- agent
- tool
- workflow
- process
- service
- capability
- trace
- relationship

### Step 8 - Operate OpenMesh Daily

User goal:

Use OpenMesh as a daily control room.

Ideal flow:

```bash
openmesh tui
openmesh doctor
openmesh snapshot create
openmesh timeline
openmesh query traces involving research-agent
```

v0.2 target:

The user returns to OpenMesh because it reduces uncertainty during real agent
work, not only because it is interesting in demos.

## 8. P0 Roadmap - Must Have

P0 is the minimum required for v0.2 to feel like a product instead of a
validated toolkit.

### P0.1 Graph-First TUI Focus Mode

Outcome:

The TUI starts to feel like a terminal-native graph explorer.

Requirements:

- Network panel remains always visible.
- Selectable graph nodes.
- Selectable graph relationships.
- Current focus shown persistently.
- Keyboard path from selected node to inspector.
- Keyboard path from selected edge to provenance.

Success metric:

A user can open `openmesh tui`, select `Research Agent`, inspect `web_search`,
and return to graph focus without leaving the TUI.

### P0.2 Entity And Relationship Inspector

Outcome:

Users can answer "why does this exist?" from the terminal.

Requirements:

- Entity inspector for node type, status, event count, relationship count,
  first seen, last seen, traces, sessions, incoming edges, outgoing edges.
- Relationship inspector for type, definition, validation state, observation
  count, first seen, last seen, trace ids, event ids, recent evidence.
- Human-readable evidence before raw ids.

Success metric:

A user can explain an edge's source evidence in under ten seconds.

### P0.3 Neighborhood Expansion And Filtering

Outcome:

Graph exploration scales beyond tiny examples.

Requirements:

- Depth 1 and depth 2 expansion.
- Type filters for agents, tools, workflows, processes, services, MCP servers,
  and capabilities.
- Relationship filters for uses, runs, transitions_to, connects_to, exposes,
  spawns, executes, communicates_with.
- Search within graph focus mode.

Success metric:

A user can move from one agent to connected tools and workflows without reading
raw event output.

### P0.4 Trace And Workflow Replay In Context

Outcome:

Replay becomes a graph experience, not only a list of frames.

Requirements:

- Trace-local replay view.
- Workflow-local replay view.
- Highlight nodes and edges created by each frame.
- Show span tree beside event sequence.
- Preserve selected entity when switching between graph, trace, and replay.

Success metric:

A user can watch `LangGraph -> workflow -> Node A -> Node B -> Node C` form in
the TUI.

### P0.5 CLI Continuation Hints

Outcome:

CLI users get guided to the next useful command.

Requirements:

- Empty graph output suggests first event command.
- `discover` suggests inspect commands for visible entities.
- `graph` suggests inspect/replay commands for visible nodes and traces.
- `inspect` suggests timeline/replay/query pivots.

Success metric:

New users can complete the first journey without returning to README.

### P0.6 Product Language Cleanup

Outcome:

Public-facing docs have one product story.

Requirements:

- Lead with OpenMesh, not OpenMeshAI simulator language.
- Clearly mark dashboard and simulator as secondary/demo layers.
- Clarify Discovery vs Ecosystem naming.
- Keep MCP metadata-only scope explicit.

Success metric:

A new user can answer "what is OpenMesh?" after reading the README intro.

## 9. P1 Roadmap - Should Have

P1 makes v0.2 stronger, but should not block release if P0 is excellent.

### P1.1 Frontend Graph Visualization Layer

Outcome:

The optional dashboard explains the graph visually.

Requirements:

- Local graph visualization over existing graph API.
- Node and edge inspector.
- Type and relationship filters.
- Timeline scrubber for graph evolution.

Success metric:

The browser view helps demos and onboarding without becoming the primary
product surface.

### P1.2 Guided Example Suite

Outcome:

Examples become a product onboarding path.

Requirements:

- `First 10 Minutes` guide.
- Core process example.
- Core Python SDK example.
- Optional LangGraph example.
- Expected graph output for each example.
- Troubleshooting links beside each example.

Success metric:

Users can produce a meaningful graph within ten minutes.

### P1.3 Plugin And Integration UX Polish

Outcome:

Integration status becomes understandable.

Requirements:

- Clear states for available, installed, active, missing package, planned.
- TUI integration view grouped by state.
- Integration docs show install and validation path.

Success metric:

Users do not confuse optional missing framework packages with OpenMesh failure.

### P1.4 Snapshot And Timeline UX Polish

Outcome:

Historical views become easier to read.

Requirements:

- Timeline grouping by event class.
- Snapshot creation guidance.
- Snapshot diff summaries in human-readable sections.
- TUI timeline mode tied to current selection.

Success metric:

Users can identify what changed between two runs without reading raw event
lists.

### P1.5 Daily Operator Workflow

Outcome:

OpenMesh becomes useful beyond demos.

Requirements:

- Recommended daily command set.
- TUI default view for active work.
- `doctor` output grouped into action-needed vs informational.
- Query shortcuts for common questions.

Success metric:

Users can keep OpenMesh open during real agent development sessions.

## 10. P2 Roadmap - Nice To Have

P2 should be considered after the graph-first v0.2 experience is stable.

### P2.1 More Framework Coverage

Potential work:

- Harden CrewAI, AutoGen, OpenHands, Claude Code, and OpenCode coverage based
  on user feedback.
- Add callback-depth improvements.
- Add more example workloads.

Constraint:

Do not add integrations at the expense of graph exploration quality.

### P2.2 Query Builder UX

Potential work:

- Saved query management.
- Query aliases.
- Interactive query selector in TUI.
- Query result pivots into graph focus.

### P2.3 Export And Sharing

Potential work:

- Export graph snapshots.
- Export timeline/replay summaries.
- Shareable static reports.

Constraint:

Exports should remain derived from existing state.

### P2.4 Hosted Docs And Visual Tutorial

Potential work:

- Hosted documentation site.
- Short terminal demos.
- Example screenshots.
- "What OpenMesh sees" visual walkthrough.

### P2.5 Performance And Scale Benchmarks

Potential work:

- Publish 100, 1,000, and 10,000 node benchmark results.
- Document practical SQLite limits.
- Document Postgres recommendations.

## 11. Success Metrics

### Activation Metrics

- Fresh install to `openmesh doctor Overall: OK` in under five minutes.
- Fresh install to first graph edge in under ten minutes.
- Fresh install to TUI graph inspection in under fifteen minutes.

### Comprehension Metrics

- New users can explain Discovery vs Ecosystem after first use.
- New users can identify which trace created a graph edge.
- New users can replay a LangGraph workflow without reading source code.

### Usability Metrics

- Fewer than three manual id copy/paste steps in the first journey.
- TUI supports graph -> inspect -> replay -> graph loop without leaving the app.
- CLI output includes next-command hints for empty and successful states.

### Reliability Metrics

- `openmesh doctor` passes on clean SQLite after core examples.
- Python SDK examples work without manually running backend startup first.
- LangGraph example produces a connected workflow graph.
- Frontend build and backend tests remain green.

### Ecosystem Metrics

- At least one polished reference framework journey.
- Integration status is understandable from CLI and TUI.
- Plugin documentation explains how future integrations should map entities and
  relationships.

## 12. Definition Of v0.2 Completion

OpenMesh v0.2 is complete when:

1. A new user can install OpenMesh, generate data, open the TUI, select a node,
   inspect a relationship, and replay a trace without reading source code.
2. The graph is the primary interaction model in CLI, TUI, docs, and optional
   dashboard concepts.
3. Entity and relationship inspectors make provenance understandable.
4. Trace and workflow replay show graph evolution, not only event lists.
5. Discovery and ecosystem views have clear product meaning.
6. The README answers "what is OpenMesh?" with one consistent product story.
7. Core examples create connected graphs and pass `openmesh doctor`.
8. Optional integrations are clearly labeled and do not look like install
   failures.
9. Release validation includes fresh install, examples, doctor, graph, inspect,
   timeline, replay, query, TUI, backend tests, and frontend build.
10. No new architecture subsystem is introduced solely for v0.2 UX; the release
    uses the existing event, trace, graph, discovery, timeline, replay, and
    query foundations.

## 13. Recommended v0.2 Release Shape

Release name:

```text
OpenMesh v0.2 - Graph Explorer Alpha
```

Release promise:

```text
OpenMesh v0.2 turns validated agent observability data into a navigable
terminal-first ecosystem graph.
```

Primary demo:

```text
install
  -> run Python SDK example
  -> run LangGraph example
  -> open TUI
  -> select Research Agent
  -> inspect web_search relationship
  -> replay LangGraph workflow
  -> show provenance
```

What v0.2 should avoid:

- Adding analysis before exploration is excellent.
- Adding many shallow integrations before one polished integration journey is
  excellent.
- Turning the dashboard into the primary product.
- Creating a second graph, trace, replay, or registry model.
- Overloading the CLI with more commands before improving command continuity.

## 14. Product North Star

OpenMesh should become the place developers go when they need to understand an
agent ecosystem as a living network.

The v0.2 north star:

```text
Every observed event should help the user move through the graph.
```


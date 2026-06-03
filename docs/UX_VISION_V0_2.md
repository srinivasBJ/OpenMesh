# OpenMesh UX Vision v0.2

Date: 2026-06-03

Scope: product and user experience design for the next OpenMesh release. This
document does not propose architecture rewrites, new integrations, protocol
changes, or implementation work.

## UX Score

Current UX score: 6.5 / 10

OpenMesh is technically strong: install, event persistence, traces, graph
provenance, discovery, timelines, replay, SDK examples, LangGraph, CLI, and TUI
are now validated. The missing layer is not data. The missing layer is
exploration.

Current OpenMesh can answer:

- What entities exist?
- What relationships exist?
- What happened over time?
- Which traces and events support a relationship?

v0.2 should make the user feel:

- I can move through the ecosystem like a map.
- I can select any entity and understand its neighborhood.
- I can replay how the network formed.
- I can pivot from graph to trace to workflow without losing context.

Target v0.2 UX score: 8.2 / 10

## 1. Current User Journey

The validated first-user path is:

```text
install
  -> openmesh doctor
  -> openmesh run -- <command>
  -> openmesh discover
  -> openmesh graph --details
  -> openmesh inspect <node_id>
  -> openmesh timeline
  -> openmesh replay
  -> openmesh tui
```

The SDK path is:

```text
python examples/python_basic_agent.py
  -> openmesh doctor
  -> openmesh discover
  -> openmesh graph --details
  -> openmesh timeline
  -> openmesh replay
  -> openmesh query traces involving <node>
```

The LangGraph path is:

```text
python -m pip install langgraph
python examples/langgraph_basic.py
  -> LangGraph --runs--> workflow
  -> Node A --transitions_to--> Node B
  -> Node B --transitions_to--> Node C
```

Current strengths:

- Commands are understandable and validated.
- `doctor` gives real integrity diagnostics.
- `graph --details` exposes provenance and relationship validation.
- `inspect` gives node-centered evidence.
- `timeline` and `replay` prove historical state can be reconstructed.
- TUI keeps the network panel visible and has a strong control-room direction.

Current issue:

The user still has to think like a database reader. They ask one command at a
time, then mentally assemble the network in their head.

## 2. Pain Points Discovered During Validation

### Graph Output Is Correct But Not Navigable

`openmesh graph --details` explains relationships, but it is a report. It does
not guide the user toward the next useful node, trace, workflow, or event.

The output is strongest for small graphs and becomes hard to scan as soon as
there are many agents, tools, workflows, MCP servers, or processes.

### Discovery And Ecosystem Views Overlap

`discover` and `ecosystem` both show inventory-like data. Their distinction is
clear to the implementation, but not necessarily to a first user.

Recommended framing:

- Discovery: what OpenMesh has observed.
- Ecosystem: the governed inventory with relationship and event counts.

### Inspect Requires Knowing The Node Id

`openmesh inspect openmesh.cli` is powerful, but users have to discover or copy
node ids manually. This breaks flow.

Better v0.2 path:

```text
openmesh discover
  -> select/copy/search entity
  -> inspect entity
  -> expand neighborhood
```

### Timeline Is Valuable But Dense

Timeline output shows events, relationship changes, workflow changes, sessions,
and snapshots. It is accurate, but it reads like a chronological log instead of
an evolution story.

Users need grouping:

- first appearances
- relationship creation
- workflow execution
- capability/MCP changes
- session windows
- snapshot checkpoints

### Replay Is Conceptually Strong But Visually Thin

Replay currently exposes frames and controls, but it does not yet make the graph
feel animated or progressive. Users should see the network grow, not only see
frame text.

### TUI Has Many Modes But A Weak Object Model

The TUI has panels, tables, graph filters, query mode, replay mode, snapshots,
discovery, ecosystem, and inspection details. It is already capable, but the
interaction model should become object-centered:

```text
select node
  -> inspect
  -> expand
  -> show traces
  -> replay local history
  -> jump to workflow
```

### Dashboard Is Secondary But Could Explain Shape Better

The browser dashboard is not the core product, but a visual graph would help
new users understand the product faster. It should visualize the same protocol
state rather than become a separate dashboard product.

## 3. Interactive Graph Concepts

Inspirations:

- Obsidian Graph View: local neighborhood expansion, filters, search, focus.
- GitHub Network Graph: commit/path lineage and branching over time.
- k9s: always-visible resource lists, fast keyboard navigation, inspect panels.
- lazygit: left-side object lists, center detail, right/bottom contextual panes.

### Core Graph Loop

```text
Search / Select
  -> Focus Node
  -> Expand Neighborhood
  -> Inspect Relationship
  -> Jump To Trace
  -> Replay Formation
```

### Terminal Graph View

The network panel should become the hero interaction surface:

```text
OPENMESH GRAPH

focus: Research Agent                         filters: agents tools workflows

Research Agent
├─ uses          -> web_search                 obs:2  last:10:35
├─ delegates_to  -> Writer Agent               obs:1  last:10:37
└─ runs          -> LangGraph Basic            obs:1  last:10:38

Neighborhood
  web_search
  Writer Agent
  LangGraph Basic
  Node A
  Node B

actions: enter inspect | e expand | t traces | r replay | / search | f filter
```

### Expansion Modes

- Depth 1: immediate relationships.
- Depth 2: neighbors of neighbors.
- Trace-local: only relationships created by a trace.
- Workflow-local: only nodes and edges in a workflow.
- Time-windowed: only relationships first seen during a time window.
- Type-filtered: agents, tools, workflows, MCP servers, capabilities, processes.

### Relationship-First Navigation

Edges should be selectable like nodes. Selecting an edge should show:

- relationship type
- definition
- source and target
- lifecycle state
- observation count
- first seen / last seen
- trace ids
- event ids
- recent evidence

This is OpenMesh's differentiator. Relationship provenance should be visible by
default, not hidden behind verbose output.

## 4. Entity Inspector Concepts

The inspector should become the user's home base for understanding any entity.

### Inspector Layout

```text
Research Agent                                      agent
status: active       first: 10:34:05       last: 10:35:51
events: 6            traces: 1             relationships: 1

Outgoing
  uses -> web_search               obs:2   trace: trace_59af...

Incoming
  none

Traces
  trace_59af...                    completed  events:6

Recent Evidence
  10:35:51 tool.call.started       evt_9fb...
  10:35:51 tool.call.completed     evt_615...

actions: g graph | t timeline | r replay | w workflow | c copy id
```

### Inspector Principles

- Always show the entity's identity and type first.
- Show relationship count before raw event count.
- Split incoming and outgoing relationships.
- Show provenance compactly, with an option to expand.
- Make trace and session pivots first-class.
- Preserve the previous graph focus when leaving the inspector.

### CLI Inspector Improvements

Potential v0.2 CLI shape:

```bash
openmesh inspect research-agent --neighbors
openmesh inspect research-agent --traces
openmesh inspect research-agent --replay
openmesh inspect research-agent --json
```

No new backend model is required. This is a presentation layer over existing
inspect, graph, timeline, and replay state.

## 5. Trace Replay Concepts

OpenTelemetry traces are useful because they turn execution into nested spans.
OpenMesh should borrow that clarity, but keep the graph visible.

### Trace Replay Goal

Given a trace:

```text
Agent
  -> Task
    -> Tool
      -> Service / MCP / Process
```

The user should see:

- span tree
- event sequence
- relationships created by the trace
- graph nodes touched by the trace
- failures or active spans, if present

### Trace Replay Screen

```text
TRACE trace_59af...                              completed

Span Tree                         Network Created
Research Agent                    Research Agent
└─ Research vector databases      └─ uses -> web_search
   └─ web_search

Events
10:35:51 agent.registered
10:35:51 task.started
10:35:51 tool.call.started
10:35:51 tool.call.completed
10:35:51 message.sent
10:35:51 task.completed

actions: space play/pause | n step | g graph | i inspect selected
```

### Replay Principles

- Replay should show network formation, not just event lines.
- Frame advancement should highlight changed nodes and edges.
- Trace-local replay should be the default before ecosystem-wide replay.
- Replay should preserve causality: parent span, child span, linked trace, edge
  provenance.

## 6. Workflow Exploration Concepts

Workflow exploration is the most natural bridge between LangGraph-like systems
and the OpenMesh graph.

### Workflow View

```text
WORKFLOW LangGraph Basic                         framework: langgraph
status: completed       trace: trace_611...      events: 8

Runtime
  LangGraph --runs--> LangGraph Basic

Flow
  Node A ──transitions_to──> Node B ──transitions_to──> Node C

Participants
  services: Node A, Node B, Node C
  tools: none
  agents: none
  mcp: none

actions: enter inspect node | r replay workflow | t trace | g focus graph
```

### Workflow UX Requirements

- Show runtime relationship first: framework/service runs workflow.
- Show transitions as a compact chain when possible.
- Expand into a table when the workflow branches.
- Connect workflow nodes to trace spans.
- Show participating agents, tools, MCP servers, services, and processes.
- Avoid analysis language. This is exploration, not diagnosis.

## 7. Control Room Improvements

The current TUI identity is correct: dark industrial, rust highlights,
control-room mood, terminal-first. v0.2 should improve hierarchy and motion.

### Always Visible Areas

- Network panel remains visible.
- Current focus is always visible.
- Status strip shows database, events, traces, nodes, edges, sessions.
- Mode strip shows graph, inspect, timeline, replay, query.

### Suggested v0.2 TUI Layout

```text
┌─ Inventory ───────────────┬─ Network / Focus Graph ─────────────────────────┐
│ Agents                    │ focus: Research Agent        depth:2  filter:all │
│ Workflows                 │                                                  │
│ Tools                     │ Research Agent                                   │
│ Processes                 │ ├─ uses -> web_search                            │
│ MCP                       │ └─ runs -> LangGraph Basic                       │
│ Capabilities              │                                                  │
├─ Timeline / Traces ───────┼─ Inspector / Events / Replay ───────────────────┤
│ trace_59af...             │ web_search                                       │
│ trace_611c...             │ type: tool    events:4    relationships:2       │
└───────────────────────────┴────────────────────────────────────────────────┘
```

### Interaction Model

- Arrow keys move selection.
- Enter inspects selected node or relationship.
- `/` searches graph entities.
- `e` expands neighborhood.
- `[` and `]` change depth.
- `f` cycles filters.
- `t` jumps to timeline for selected entity.
- `r` replays selected trace/workflow/entity history.
- `g` returns focus to graph.
- `c` copies selected id.

### Visual Hierarchy

- Rust orange: selected row, current focus, active relationship.
- Steel gray: secondary metadata, timestamps, provenance ids.
- Dark iron: background surfaces.
- Red only for failed state.
- Yellow only for warnings.
- Avoid neon colors and decorative noise.

## 8. Terminal-First UX Principles

1. The graph is the product.

Every view should either show the graph, explain part of the graph, or help the
user move through the graph.

2. Preserve context.

If the user selects `Research Agent`, then moves to timeline, replay, or trace,
OpenMesh should remember that focus.

3. Prefer progressive disclosure.

Default output should show the most useful five things. Details should be one
keystroke away.

4. Make provenance readable.

Raw event ids matter, but first show human-scale evidence:

```text
created by tool.call.started at 10:35:51 in trace_59af...
```

5. Avoid dashboard thinking.

The terminal experience should not imitate a web analytics page. It should feel
like an operating console for a live agent network.

6. Commands should compose.

CLI output should help users continue:

```text
next: openmesh inspect research-agent
next: openmesh replay trace trace_59af...
```

7. Empty states should teach the first action.

Instead of only:

```text
No OpenMesh graph nodes found.
```

Use:

```text
No OpenMesh graph nodes found.
Run: openmesh run -- python -c "print('hello openmesh')"
```

## 9. Frontend Graph Visualization Concepts

The dashboard remains secondary, but v0.2 should use it to make the graph easier
to understand visually.

### Frontend Role

- Visual explanation layer.
- Snapshot and diff browser.
- Graph neighborhood viewer.
- Trace and workflow playback canvas.

Not the primary control surface.

### Visual Graph Concepts

Borrow from Obsidian Graph View:

- Force-directed graph for local neighborhoods.
- Search box with highlighted matches.
- Filters for node type and relationship type.
- Click node -> inspector.
- Click edge -> provenance.
- Pin/focus selected node.

Borrow from GitHub Network Graph:

- Timeline scrubber.
- Branching workflow/relationship evolution.
- Snapshot checkpoints.
- Diff between two graph states.

Borrow from OpenTelemetry:

- Span tree beside graph changes.
- Trace duration and status.
- Parent-child nesting.
- Links and cross-trace references.

### Frontend First Screen

The first screen should not be a generic dashboard. It should be:

```text
OpenMesh Network
  graph canvas
  selected entity inspector
  recent relationship changes
  trace replay strip
```

## 10. Prioritized Roadmap

### P0 - Make Graph Exploration The Main Loop

Why: This is the product differentiator.

Deliverables:

- TUI graph focus mode.
- Selectable nodes and relationships.
- Neighborhood expansion from current selection.
- Search and filters integrated into graph mode.
- Inspector opens without requiring manually copied node ids.

Success metric:

A user can start from `openmesh tui`, select an agent, inspect its tools,
follow a workflow, and replay the trace without leaving the TUI.

### P1 - Improve Inspector And Provenance Readability

Why: Users need to trust why an edge exists.

Deliverables:

- Entity inspector with incoming/outgoing relationships.
- Edge inspector with evidence summary.
- Trace/session/event pivots.
- Human-readable provenance before raw ids.

Success metric:

A user can answer "why does this relationship exist?" in under ten seconds.

### P2 - Trace And Workflow Replay As Visual Timelines

Why: Replay is a powerful concept, but needs a stronger visual form.

Deliverables:

- Trace-local replay first.
- Workflow replay with node transition highlighting.
- Frame-by-frame graph changes.
- Span tree beside event stream.

Success metric:

A user can watch `Node A -> Node B -> Node C` form in the TUI or dashboard.

### P3 - Clarify Discovery vs Ecosystem

Why: These are both useful, but their product roles overlap.

Deliverables:

- Discovery becomes "Observed".
- Ecosystem becomes "Inventory".
- Shared entity cards/rows across CLI and TUI.
- Empty states suggest first actions.

Success metric:

New users can explain the difference after seeing both views once.

### P4 - Frontend Local Graph Viewer

Why: The dashboard is secondary, but a graph canvas helps users understand the
model quickly.

Deliverables:

- Local graph visualization over `/api/openmesh/graph`.
- Node and edge inspector.
- Filters and search.
- Timeline scrubber.

Success metric:

The frontend helps explain OpenMesh during demos without becoming the primary
product surface.

### P5 - CLI Continuation Hints

Why: CLI commands should guide exploration.

Deliverables:

- `openmesh graph` suggests inspect/replay commands.
- `openmesh inspect` suggests timeline/replay/query commands.
- `openmesh discover` shows copyable ids or direct next commands.

Success metric:

Users do not need README open after the first successful run.

## Recommended v0.2 Experience

The best v0.2 experience is:

```text
openmesh tui
  -> graph-first control room
  -> select entity
  -> inspect relationships
  -> expand neighborhood
  -> replay trace/workflow
  -> pivot back to graph
```

The CLI remains essential, but it should act as a fast path into the same object
model:

```bash
openmesh discover
openmesh inspect research-agent
openmesh graph --focus research-agent --depth 2
openmesh replay trace trace_59af...
```

The frontend should become an optional visual graph lens, not a dashboard-first
product.

## Current Limitations

- Graph output is static text, not an exploration loop.
- TUI has many modes, but selection and inspection need stronger continuity.
- Discovery and ecosystem views overlap conceptually.
- Timeline is accurate but reads like a log.
- Replay is frame-based but does not yet feel like graph evolution.
- Inspector depends too much on knowing ids ahead of time.
- Frontend does not yet visualize the OpenMesh graph as the primary object.
- Empty states do not consistently teach the next action.

## Priority Ranking

1. TUI graph focus mode with selectable nodes and relationships.
2. Entity and relationship inspector improvements.
3. Trace/workflow replay tied to graph highlighting.
4. Search, filters, and neighborhood expansion as first-class TUI actions.
5. CLI continuation hints and focus/depth graph commands.
6. Rename/framing pass for Discovery vs Ecosystem.
7. Frontend graph visualization layer.
8. Empty-state and onboarding polish.

## Product Principle

OpenMesh v0.1 proved the architecture.

OpenMesh v0.2 should make the graph feel alive.


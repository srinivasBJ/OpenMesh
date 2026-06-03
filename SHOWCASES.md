# OpenMesh Showcase Scenarios

These scenarios seed realistic OpenMesh data through the existing SDK,
collector, persistence, graph, discovery, timeline, and replay pipeline.

They do not bypass OpenMesh internals and do not create a second graph model.

## Run All Showcases

Use a dedicated SQLite database when you want a clean demo:

```bash
export OPENMESH_SQLITE_PATH=/tmp/openmesh-showcases.db
python examples/showcase_all.py
```

Then inspect the result:

```bash
openmesh discover
openmesh ecosystem
openmesh graph --stats --details
openmesh timeline
openmesh replay
openmesh tui
```

For the browser graph view:

```bash
cd backend
OPENMESH_SQLITE_PATH=/tmp/openmesh-showcases.db \
  python -m uvicorn src.main:app --host 127.0.0.1 --port 8000

cd frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173/graph
```

## Multi-Agent Research Workflow

Command:

```bash
python examples/showcase_multi_agent_research.py
```

Expected entities:

- Research Agent
- Planner Agent
- Writer Agent
- web_search
- document_store
- Multi-Agent Research Brief workflow

Expected relationships:

- Planner Agent runs Multi-Agent Research Brief
- Planner Agent delegates_to Research Agent
- Planner Agent delegates_to Writer Agent
- Research Agent uses web_search
- Planner Agent uses document_store
- Writer Agent uses document_store
- agents communicate_with each other

Expected timeline:

- workflow started
- task started/completed spans for all three agents
- tool calls
- message handoffs
- workflow completed

## LangGraph Showcase

Command:

```bash
python examples/showcase_langgraph.py
```

Expected entities:

- LangGraph
- LangGraph Showcase Branching Workflow
- Classify Topic
- Deep Research
- Risk Review
- Rank Sources
- Rank Sources Retry
- Synthesize Answer

Expected relationships:

- LangGraph runs LangGraph Showcase Branching Workflow
- workflow nodes transition to downstream nodes
- branch transitions from Classify Topic to Deep Research and Risk Review
- retry transition from Rank Sources to Rank Sources Retry

Expected timeline:

- workflow started
- node.started and node.completed events
- node.failed for the first Rank Sources attempt
- retry node execution
- workflow completed

## MCP Ecosystem Showcase

Command:

```bash
python examples/showcase_mcp_ecosystem.py
```

Expected entities:

- MCP Coordinator Agent
- Claude Desktop Config
- Filesystem MCP
- Search MCP
- file_system
- web_search
- read_project_file capability
- write_report capability
- web_search capability

Expected relationships:

- config source defines MCP servers
- MCP servers expose capabilities
- tools connect to MCP servers
- MCP Coordinator Agent uses file_system and web_search

Expected timeline:

- MCP config discovery
- capability discovery
- tool to server relationships
- agent task and tool calls

## Graph Evolution Showcase

Command:

```bash
python examples/showcase_graph_evolution.py
```

Expected entities:

- Evolution Agent
- Reviewer Agent
- relationship_analyzer
- Graph Evolution Demo workflow
- reports/openmesh-graph-evolution.md

Expected relationships:

- Evolution Agent uses relationship_analyzer
- Evolution Agent runs Graph Evolution Demo
- Evolution Agent modifies report file
- Evolution Agent communicates_with Reviewer Agent
- Reviewer Agent communicates_with Evolution Agent

Expected timeline:

- agent created
- tool attached
- workflow started
- relationships added
- artifact modified
- workflow completed

## Graph View Checks

In `/graph`:

- Search for `Research Agent` and select the node.
- Filter entity type to `workflow`.
- Select a trace in the Trace Integration panel.
- Confirm related nodes and relationships highlight.
- Inspect relationship provenance in the right panel.
- Use zoom, pan, depth, lifecycle, entity, and relationship controls.

## Replay Checks

Use trace ids printed by each scenario:

```bash
openmesh trace <trace_id>
openmesh timeline trace <trace_id>
openmesh replay trace <trace_id>
```

Replay should show node appearance, relationship creation, workflow evolution,
tool usage, session progression, and trace events derived from persisted
history.

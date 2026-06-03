# OpenMesh v0.1 Release

OpenMesh v0.1 is the first release focused on terminal-first observability for agent ecosystems.

The release proves the core architecture:

```text
SDK / CLI / integrations
  -> OpenMesh collector
  -> event persistence
  -> traces, graph, discovery, diagnostics
  -> CLI, TUI, API, and dashboard consumers
```

## Release Readiness Score

**8.1 / 10**

OpenMesh v0.1 is ready for an alpha release to technical users who are comfortable with Python packaging, local SQLite/Postgres configuration, and evolving APIs.

It is not yet ready for a broad nontechnical release because package publishing, clean-environment smoke tests, hosted documentation, and compatibility guarantees still need one more pass.

## Features

- OpenMesh event schema with source, target, payload, metrics, severity, trace, span, parent, root, and link fields.
- Central collector service for validation, persistence, graph updates, and broadcasts.
- Protocol-native event persistence alongside legacy application tables.
- Trace reconstruction with hierarchy, span tree, lifecycle, links, and graph relationships.
- Graph reducer with governed node types, relationship types, provenance, lifecycle state, and validation.
- Discovery registry for observed frameworks, agents, tools, workflows, processes, services, capabilities, and MCP metadata.
- Unified ecosystem registry for grouped entity inventory.
- Diagnostics through `openmesh doctor`.
- SQLite local mode and Postgres support.
- CLI consumer and process observation through `openmesh run -- <command>`.
- Terminal UI through `openmesh tui`.
- Python SDK v0.1 with sync and async agent/task/tool contexts.
- FastAPI routes for events, traces, graph, sessions, discovery, ecosystem, integrations, registries, workflows, MCP metadata, and capabilities.
- Existing React dashboard remains available as a visualization layer.

## Integrations

### Python SDK

```python
from openmesh import OpenMeshClient

client = OpenMeshClient()
agent = client.agent(id="research-agent", name="Research Agent")

with agent.task("Research vector databases"):
    with agent.tool("web_search"):
        pass
```

Async usage is supported:

```python
async with agent.task("Research"):
    async with agent.tool("web_search"):
        await agent.emit_async("message.sent", {"message": "done"})
```

### LangGraph

LangGraph is the first reference framework integration. It observes workflow nodes and transitions.

```bash
python -m pip install langgraph
python examples/langgraph_basic.py
```

Emits:

- `workflow.started`
- `node.started`
- `node.completed`
- `node.failed`
- `node.transition`
- `workflow.completed`

### CrewAI

CrewAI is the second reference framework integration. It observes agents, tasks, tools, and crew workflows.

```bash
python examples/crewai_basic.py
```

Emits:

- `workflow.started`
- `agent.registered`
- `workflow.registered`
- `node.started`
- `task.started`
- `tool.call.started`
- `tool.call.completed`
- `task.completed`
- `node.transition`
- `workflow.completed`

The CrewAI integration observes lifecycle metadata only. It does not execute CrewAI tools, inspect credentials, call LLMs, or perform analysis.

## Install Instructions

Editable install from the repository root:

```bash
python -m pip install -e .
```

After package publication:

```bash
python -m pip install openmesh
```

Local SQLite mode:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
```

Validate the install:

```bash
openmesh doctor
openmesh discover
openmesh ecosystem
openmesh graph
openmesh integrations
openmesh tui --once
python -c "from openmesh import OpenMeshClient; print(OpenMeshClient.__name__)"
```

## CLI Commands

The v0.1 CLI documents and validates these commands:

- `openmesh doctor`
- `openmesh health`
- `openmesh events`
- `openmesh traces`
- `openmesh trace <trace_id>`
- `openmesh graph`
- `openmesh graph --details`
- `openmesh nodes`
- `openmesh discover`
- `openmesh ecosystem`
- `openmesh workflows`
- `openmesh capabilities`
- `openmesh integrations`
- `openmesh registry`
- `openmesh mcp`
- `openmesh mcp-config`
- `openmesh run -- <command>`
- `openmesh tui`
- `openmesh tui --once`

## Examples

Run from the repository root after installing OpenMesh:

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
python examples/crewai_basic.py
```

LangGraph requires the external package:

```bash
python -m pip install langgraph
python examples/langgraph_basic.py
```

After running examples, inspect activity:

```bash
openmesh discover
openmesh ecosystem
openmesh graph --details
openmesh traces
openmesh trace <trace_id>
openmesh tui --once
```

## Release Notes

### Architecture

OpenMesh v0.1 establishes a collector-centered architecture. Events flow through one collector path into durable storage, then traces, graph state, discovery, registry views, diagnostics, CLI, TUI, API, and dashboard views are derived from that stored protocol data.

### Ecosystem Mapping

The graph layer now has governed node and relationship vocabularies. Edges include provenance fields such as trace id, event id, first seen, last seen, and observation count.

The ecosystem registry unifies agents, tools, processes, workflows, MCP servers, MCP configs, and capabilities into one inventory view.

### Discovery

Discovery is event-derived. OpenMesh can catalog observed frameworks, agents, tools, workflows, processes, services, MCP metadata, and capability metadata without creating a separate registry pipeline.

### Diagnostics

`openmesh doctor` reports database, migration, collector, integration, trace, workflow, graph, node, relationship, registry compatibility, MCP config, capability, workflow registry, and ecosystem integrity checks.

### Integrations

LangGraph and CrewAI are reference integrations. Both use the Python SDK and existing collector pipeline. Neither creates a parallel storage or analysis path.

## Known Limitations

- v0.1 is alpha-quality and API details may still change.
- `pip install openmesh` depends on publishing the package to PyPI; local validation currently uses editable installs and wheel builds.
- LangGraph is optional and must be installed separately to run `examples/langgraph_basic.py`.
- CrewAI observation is lifecycle and metadata oriented. It does not monkeypatch CrewAI internals or inspect live tool execution.
- MCP discovery is metadata-only. OpenMesh does not connect to MCP servers, execute MCP tools, perform health checks, or run security analysis.
- The TUI is functional but intentionally simple. It is not yet a full k9s-style interactive operations surface.
- The dashboard remains a temporary visualization layer and is not the primary interface.
- Some legacy simulator and dashboard surfaces remain in the repository while the protocol-first architecture matures.
- Running all examples into the same database can produce expected `doctor` warnings or errors for duplicate display names, such as multiple `Research Agent` or `web_search` entities from different integrations.
- The LangGraph example currently records workflow metadata without a `source` field, which `openmesh doctor` reports as workflow registry metadata that should be improved before a broader release.
- Clean virtual environment and TestPyPI validation should be completed before public package announcement.

## Missing Items Before Public Release

- Publish package artifacts to TestPyPI and validate clean install.
- Verify `pip install openmesh` after PyPI publication.
- Add package build automation to CI.
- Confirm license metadata and package classifiers.
- Decide whether duplicate local artifacts should be removed or ignored before tagging.
- Normalize example metadata so combined-example doctor output is clean or clearly documented.
- Create a final release tag and GitHub release.

## Risks Before Release

- Packaging path behavior may differ across platforms because the repo has a space in its local path and uses an installable launcher script.
- Framework integration APIs are early and should be considered experimental.
- Graph and registry semantics are governed, but future vocabulary expansion may require migration guidance.
- SQLite mode is excellent for local usage but does not represent production concurrency behavior.
- Existing frontend and simulator code still carry older product concepts that may confuse contributors unless documentation clearly frames them as legacy/visualization layers.
- Some release validation commands are dataset-sensitive: `openmesh doctor` is stricter after mixed examples because duplicate names and missing optional metadata are reported as integrity issues.

## Recommended v0.2 Priorities

- Add clean-environment release CI for wheel install, CLI smoke tests, and example smoke tests.
- Add trace/session filters to CLI and API.
- Improve TUI inspection for selected traces, nodes, and relationships.
- Add AutoGen or OpenHands as the next framework integration after stabilizing the integration API.
- Improve process observation metadata.
- Add API tests for OpenMesh routes.
- Publish hosted documentation for install, SDK, integrations, CLI, TUI, and diagnostics.
- Keep MCP analysis, health checks, security inspection, and root-cause analysis out of scope until the registry and trace layers are stable.

# OpenMesh v0.1.0-alpha Release Notes

OpenMesh v0.1.0-alpha is the first public alpha release focused on terminal-first observability for agent ecosystems.

The release proves the core architecture:

```text
SDK / CLI / integrations
  -> OpenMesh collector
  -> event persistence
  -> traces, graph, discovery, diagnostics
  -> CLI, TUI, API, and dashboard consumers
```

## Highlights

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
- LangGraph reference integration.
- CrewAI reference integration.
- Existing React dashboard remains available as a visualization layer.

## Install

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

Validate:

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

## Known Limitations

- This is an alpha release and APIs may still change.
- `pip install openmesh` requires publishing the package to PyPI.
- LangGraph is optional and must be installed separately for the LangGraph example.
- CrewAI observation is lifecycle and metadata oriented; it does not monkeypatch CrewAI internals or inspect live tool execution.
- MCP discovery is metadata-only. OpenMesh does not connect to MCP servers, execute MCP tools, perform health checks, or run security analysis.
- The TUI is functional but intentionally simple.
- The dashboard remains a visualization layer and is not the primary interface.
- Running all examples into the same database can produce expected `doctor` warnings or errors for duplicate display names.
- The LangGraph example currently records workflow metadata without a `source` field.
- TestPyPI validation should be completed before a broader package announcement.

## Recommended Next Steps

- Complete TestPyPI validation.
- Let GitHub Actions release validation pass on the remote branch.
- Normalize example metadata.
- Add API route tests for OpenMesh protocol endpoints.
- Improve TUI inspection for traces, nodes, and relationships.
- Keep MCP execution, security analysis, and root-cause analysis out of scope until the observability layer is stable.

# OpenMesh MCP & Tool Ecosystem Observability

OpenMesh can passively discover MCP configuration sources and represent MCP
servers, tools, and resources as governed graph entities.

This phase is metadata and observability only. OpenMesh does not connect to MCP
servers, execute MCP tools, inspect credentials, run health checks, or perform
security analysis.

## Discover MCP Servers

```bash
openmesh mcp discover
```

Discovery scans known configuration and manifest locations:

- Claude Desktop configs
- Claude Code configs
- Cursor configs
- OpenCode configs
- OpenHands configs
- local MCP manifests
- project MCP manifests

You can pass an explicit source path:

```bash
openmesh mcp discover --path Project=./mcp.json
```

Example output:

```text
MCP Discovery

filesystem-server
github-server
postgres-server
memory-server
```

## Events

MCP and tool observations emit normal OpenMesh events:

```text
mcp.connected
mcp.disconnected
tool.registered
tool.called
tool.completed
tool.failed
resource.discovered
resource.accessed
```

All events flow through `OpenMeshCollector.accept()` and are stored in the same
OpenMesh event table as simulator, SDK, provider, runtime, and process events.

## Graph Relationships

The graph reducer maps MCP events into governed relationships:

```text
Agent -> uses -> MCP Server
MCP Server -> exposes -> Tool
Agent -> calls -> Tool
Tool -> accesses -> Resource
```

Relationship provenance includes event ids, trace ids, session ids, timestamps,
span ids, and observation counts.

## Resource Types

OpenMesh represents common MCP resource targets as governed node types:

- File
- Database
- GitHub Repository
- API Endpoint
- Memory Store

These resources appear in:

```bash
openmesh resources
```

Tools appear in:

```bash
openmesh tools
```

## API

```text
GET /api/openmesh/mcp
GET /api/openmesh/tools
GET /api/openmesh/resources
GET /api/openmesh/mcp/metrics
```

## Observatory Metrics

The Observatory shows MCP and tool ecosystem counters:

- active MCP servers
- tool calls
- failed tool calls
- most used tools
- resource activity

These metrics are operational read models, not analysis or recommendations.

## Safety Boundaries

OpenMesh MCP observability is intentionally passive:

- no MCP tool execution
- no live server connection required
- no credential capture
- no authentication analysis
- no capability execution
- no security scoring

Future analysis can build on these events and graph relationships, but this
phase only maps the ecosystem.

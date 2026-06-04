# Failure Intelligence

OpenMesh Failure Intelligence turns existing error and `*.failed` events into explainable graph entities. It does not add a new database or a separate analysis pipeline. It derives failures from persisted OpenMesh events, classifies them, and emits normal OpenMesh failure events through the collector.

## Failure Taxonomy

Supported categories:

- `model_failure`
- `tool_failure`
- `mcp_failure`
- `handoff_failure`
- `context_failure`
- `timeout_failure`
- `permission_failure`
- `resource_failure`

Classification is deterministic. OpenMesh looks at:

- event type
- severity
- source and target node types
- error text
- error type
- provider/tool/model/resource metadata

## Failure Events

Failure intelligence emits:

- `failure.detected`
- `failure.classified`
- `failure.resolved`

These events use the normal OpenMesh event schema and are persisted by the existing collector.

## Graph Model

New governed node:

```text
failure
```

New governed relationships:

```text
failure -> affects -> agent
failure -> affects -> workflow
failure -> caused_by -> tool
failure -> caused_by -> resource
```

Resources include files, databases, GitHub repositories, API endpoints, memory stores, services, models, processes, and MCP servers.

## Root Cause and Impact

For each failure, OpenMesh derives:

- upstream cause
- downstream impact
- affected agents
- affected workflows
- source event
- trace id
- session id

This is evidence-based infrastructure, not AI summarization.

## CLI

Detect and list failures:

```bash
openmesh failures
```

Inspect one failure:

```bash
openmesh failure inspect failure:<event_id>
```

Generate an aggregate report:

```bash
openmesh failure report
```

## APIs

```http
GET /api/openmesh/failures
GET /api/openmesh/failures/report
GET /api/openmesh/failures/{failure_id}
```

By default, API reads are non-mutating. The CLI persists newly detected failure events so graph views can inspect failure nodes and provenance.

## Observatory

The Observatory displays:

- failure count
- failure rate
- active failures
- resolved failures
- MTTR
- most common failures
- failing agents
- failing tools

## Validation

Recommended validation:

```bash
openmesh failures
openmesh failure report
openmesh doctor
python -m unittest discover -s backend/tests
npm run build
```

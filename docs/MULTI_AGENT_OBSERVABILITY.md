# Multi-Agent Handoff Observability

OpenMesh treats agent-to-agent handoffs and messages as first-class graph evidence.
The goal is to show how work moves through an agent system without requiring an
external LLM, cloud service, or framework integration.

## Events

The multi-agent workflow emits protocol-native OpenMesh events:

- `workflow.started`
- `workflow.completed`
- `agent.handoff.started`
- `agent.handoff.completed`
- `agent.message.sent`
- `agent.message.received`

Each event is persisted through the collector and carries `trace_id`, `session_id`,
`span_id`, `parent_span_id`, and event provenance.

## Relationships

The graph reducer derives:

- `agent -> delegates_to -> agent`
- `agent -> communicates_with -> agent`
- `agent -> reviews -> agent`
- `workflow -> contains -> agent`

Review edges are explicit metadata on completed handoffs. Normal handoffs remain
`delegates_to`.

## Demo

Generate a local multi-agent workflow:

```bash
openmesh run-demo multi-agent
```

Custom size:

```bash
openmesh run-demo multi-agent --agents 5 --handoffs 24 --messages 60
```

Then inspect the result:

```bash
openmesh workflows
openmesh workflow inspect workflow:openmesh:multi-agent-handoff-demo
openmesh workflow replay workflow:openmesh:multi-agent-handoff-demo
openmesh timeline workflow workflow:openmesh:multi-agent-handoff-demo
openmesh graph --details
```

## API

- `GET /api/openmesh/workflows`
- `GET /api/openmesh/workflow/{workflow_id}`
- `GET /api/openmesh/workflows/{workflow_id}`
- `GET /api/openmesh/workflows/metrics`
- `GET /api/openmesh/replay/workflow/{workflow_id}`
- `GET /api/openmesh/timeline/workflow/{workflow_id}`

## Observatory Metrics

The Observatory shows:

- active workflows
- completed workflows
- average handoffs
- busiest agent
- handoff latency

These values are derived from stored OpenMesh events.

# OpenMesh Integrations

OpenMesh integrations are plugin-discovered adapters that emit Protocol v1
events through the Python SDK and collector pipeline.

Current integrations:

- LangGraph
- CrewAI
- AutoGen
- OpenHands
- Claude Code
- OpenCode

All integrations preserve the same path:

```text
integration plugin
  -> OpenMesh SDK
  -> collector
  -> event store
  -> traces, graph, discovery, inspection, snapshots, timelines, replay, query
```

Use:

```bash
openmesh plugins
openmesh integrations
openmesh discover
openmesh graph --details
openmesh inspect <node_id>
openmesh snapshot create
openmesh timeline
openmesh replay
openmesh query agents using <tool>
```

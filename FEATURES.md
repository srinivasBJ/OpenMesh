# OpenMesh Features

## Core

- OpenMesh event schema and collector.
- SQLite and Postgres persistence.
- Trace, span, parent-child, and links semantics.
- Session tracking for observed processes.
- Graph reduction with provenance and registry validation.
- Discovery and unified ecosystem registry.
- Timeline and replay derived from persisted history.
- Snapshot and snapshot diff engine.
- Structured query engine.
- Diagnostics through `openmesh doctor`.

## Observability

- Provider observability for OpenAI, Anthropic, OpenRouter, Ollama, LM Studio,
  and vLLM.
- Runtime observability for local coding-agent tools.
- MCP server/config/tool/resource metadata observability.
- Multi-agent handoff and workflow observability.
- Failure intelligence, agent reputation, and agent genome profiles.
- OpenTelemetry export to OTLP, Tempo, Jaeger, Datadog, and Prometheus formats.

## Interfaces

- CLI command surface.
- Terminal UI control room.
- FastAPI API and WebSocket stream.
- React dashboard and graph view.
- Python SDK and async SDK.

## Integrations

Built-in plugin metadata exists for:

- LangGraph
- CrewAI
- AutoGen
- OpenHands
- Claude Code
- OpenCode

Optional framework packages are not installed by default.

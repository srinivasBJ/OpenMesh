# OpenMesh Decisions

## Dashboard Is A Consumer

The dashboard remains part of the project, but it does not define the protocol. It reads OpenMesh events, traces, and graph state like any other consumer.

## Collector First

All runtime events should pass through `OpenMeshCollector.accept()` so validation, persistence, and broadcast behavior stay centralized.

## SQLite For Local Development

Postgres is still useful for deployed or shared environments, but local development should not require Docker. SQLite mode exists for fast local startup and CLI experimentation.

## Standard Library Tests

The first test suite uses `unittest` so tests can run without adding a new test framework. This keeps the baseline repeatable in constrained environments.

## Process Observation Before SDKs

`openmesh run -- <command>` is the first external runtime integration. SDKs and framework integrations should wait until this lower-level observation path is stable.

## LangGraph Is The First Reference Integration

LangGraph is the first framework integration because its node and edge execution model aligns naturally with OpenMesh graph and trace architecture.

LangGraph nodes emit lifecycle events. LangGraph transitions emit graph relationships. This proves the SDK -> collector -> persistence -> traces -> graph path without adding a parallel pipeline.

## CrewAI Is The Second Reference Integration

CrewAI is the second official integration because its agent, task, tool, and crew workflow concepts map directly onto OpenMesh nodes, spans, traces, and graph relationships.

The CrewAI adapter observes metadata and lifecycle boundaries only. It does not execute tools, inspect credentials, analyze results, or create a parallel event pipeline.

## Event-Derived Registries

Discovery, workflow, MCP metadata, capability, and ecosystem registries are derived from stored OpenMesh events.

OpenMesh v0.1 avoids manual registry mutation as the primary source of truth. This keeps the collector and event store at the center of the architecture.

## Snapshots Are Frozen Reducer Outputs

Ecosystem snapshots are persisted point-in-time exports produced from existing OpenMesh events, sessions, graph reducer, discovery, workflow, MCP, capability, and ecosystem registries.

Snapshots do not introduce a second graph system, analysis engine, health score, or recommendation layer. They preserve what OpenMesh observed at creation time so CLI, TUI, and API consumers can inspect the ecosystem later.

## Active Analysis Is Future Work

MCP endpoint health checks, capability discovery, tool inventory generation, authentication analysis, permission visibility, dependency mapping, trust-chain mapping, and security posture insights belong on the roadmap.

They should remain future analysis layers built on top of OpenMesh discovery, registry, relationship mapping, and observability data.

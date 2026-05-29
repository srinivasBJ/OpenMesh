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

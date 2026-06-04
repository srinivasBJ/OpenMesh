# OpenMesh Roadmap

This file mirrors the current launch roadmap in the repository root:
[../ROADMAP.md](../ROADMAP.md).

Use this copy when browsing docs directly.

## Current State

OpenMesh v1.0 Alpha is published as `v1.0.0-alpha`.

The current architecture is:

```text
Observe
-> Event
-> Trace / Span / Session
-> Graph + Provenance
-> Discovery
-> Inspection
-> Snapshot
-> Diff
-> Timeline
-> Replay
-> Query
```

Validated alpha capabilities:

- Fresh macOS clone to populated graph in under five minutes.
- SQLite local mode with no Docker, Postgres, API keys, or local model servers.
- CLI, TUI, backend API, frontend routes, graph, timeline, workflow replay, and
  observatory routes.
- Python package wheel build as `openmesh-1.0.0a0`.

## Immediate Priorities

P0 alpha stabilization:

- Resolve or document frontend dependency audit findings.
- Add automated browser route and console smoke tests.
- Add pagination/windowing for graph, timeline, replay, query, and genome APIs.
- Add API response-size budgets.
- Add contributor issue labels and a first-contribution board.
- Add command recipes and `--json` examples.
- Revalidate Dependabot PRs after the alpha tag in a separate hardening batch.

## V1 Beta Priorities

- Add optional dependency extras such as `openmesh[langgraph]`,
  `openmesh[crewai]`, `openmesh[providers]`, and `openmesh[dev]`.
- Add reproducible real-world integration fixtures.
- Add OpenTelemetry collector interoperability tests.
- Add supported Docker Compose path for API plus frontend.
- Add SQLite migration rollback and backup checks.
- Add synthetic 100, 1,000, and 10,000 node stress reports.
- Add graph/timeline/replay filtering for larger datasets.

## V1.0 Stable Candidate

- Define supported single-node deployment.
- Document retention, backup, and migration procedures.
- Add release automation for wheel build, artifact inspection, tag validation,
  and GitHub release publication.
- Add protocol and registry compatibility tests.
- Add plugin packaging fixtures.
- Add read-only API auth option for self-hosted deployments.

## Later Phases

Cloud foundation:

- Hosted OpenMesh deployment.
- Multi-user organizations.
- Team workspaces.
- Hosted event storage.
- Shared observability dashboards.

Ecosystem integrations:

- LangSmith integration.
- OpenTelemetry interoperability hardening.
- Datadog export hardening.
- Grafana Tempo export hardening.
- Prometheus export hardening.

Enterprise:

- RBAC.
- SSO.
- Audit logs.
- Compliance reporting.
- Team governance.

Agent network:

- Public agent registry.
- Public workflow registry.
- Community-shared observability packs.
- Agent reputation network.

## Not Yet

Defer these until graph, trace, replay, and query paths are fast, boring, and
well-tested:

- AI root-cause analysis.
- Security posture scoring.
- Permission and trust-chain analysis.
- Live MCP capability execution.
- Automated remediation.
- Hosted multi-tenant governance.

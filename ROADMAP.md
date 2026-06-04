# OpenMesh Roadmap

Last updated: 2026-06-04

OpenMesh v1.0 Alpha is published as `v1.0.0-alpha`.

This roadmap starts from the current shipped architecture:

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

OpenMesh should keep evolving as a terminal-first, graph-first observability
platform for AI agent ecosystems. The dashboard remains a visualization layer;
the durable product center is the protocol, collector, CLI/TUI, graph,
provenance, and ecosystem registry.

## Current Release State

Status: v1.0 Alpha.

Validated:

- Fresh macOS clone to populated graph in under five minutes.
- SQLite local mode with no Docker, Postgres, API keys, or local model servers.
- CLI, TUI, backend API, frontend routes, graph, timeline, workflow replay, and
  observatory routes.
- Python package wheel build as `openmesh-1.0.0a0`.
- GitHub prerelease: `v1.0.0-alpha`.

Current readiness:

- V1 Alpha readiness: 88%.
- V1.0 readiness: 58%.
- Final alpha readiness score: 7.8/10.

## Product Principles

- Keep OpenMesh terminal-first and graph-first.
- Prefer evolution over architecture rewrites.
- Do not introduce a second graph model, second event store, or parallel
  collector pipeline.
- Keep snapshots, diffs, timelines, replays, and queries derived from persisted
  OpenMesh history.
- Keep integrations SDK/protocol-backed rather than special-case graph writers.
- Keep local no-key onboarding excellent.
- Treat cloud, enterprise, and AI analysis as later layers on top of reliable
  observability data.

## Phase 0 - V1 Alpha Launch

Status: complete.

Completed:

- Event, trace, span, session, graph, provenance, discovery, inspection,
  snapshot, diff, timeline, replay, and query foundations.
- CLI and TUI.
- Frontend graph/control-room experience.
- Python SDK with sync and async support.
- Framework/runtime/provider/MCP/export surfaces.
- Simulation engine for realistic no-key data.
- Fresh install validation.
- Release docs and launch verification.

Release artifacts:

- [docs/RELEASE_NOTES_V1_ALPHA.md](docs/RELEASE_NOTES_V1_ALPHA.md)
- [docs/LAUNCH_VERIFICATION.md](docs/LAUNCH_VERIFICATION.md)
- [docs/V1_ALPHA_READINESS.md](docs/V1_ALPHA_READINESS.md)
- [docs/FRESH_INSTALL_VALIDATION.md](docs/FRESH_INSTALL_VALIDATION.md)

## Phase 1 - Alpha Stabilization

Goal: make the public alpha easier to install, test, demo, and contribute to.

Priority: P0.

Work items:

- Resolve or formally document frontend dependency audit findings.
- Add automated browser route and console smoke tests.
- Add response pagination/windowing for graph, timeline, replay, query, and
  genome APIs.
- Add API response-size budgets and regression tests.
- Add contributor issue labels and a first-contribution issue board.
- Add command recipes for the top five workflows:
  - no-key demo graph
  - workflow replay
  - process observation
  - provider discovery
  - frontend graph inspection
- Add `--json` examples for scriptable CLI usage.
- Revalidate Dependabot PRs after the alpha tag and merge safe dependency
  hardening PRs in a separate post-alpha batch.
- Standardize the canonical repository URL everywhere as
  `https://github.com/srinivasBJ/OpenMesh`.

Exit criteria:

- Browser route smoke is part of CI.
- Fresh install remains green.
- Dependency warnings are either fixed or explicitly accepted.
- External contributors can find scoped starter work quickly.

## Phase 2 - V1 Beta Readiness

Goal: harden the architecture for broader external testing.

Priority: P0/P1.

Work items:

- Add optional dependency extras such as:
  - `openmesh[langgraph]`
  - `openmesh[crewai]`
  - `openmesh[providers]`
  - `openmesh[dev]`
- Add real-world integration fixtures that do not require secrets.
- Add OpenTelemetry collector interoperability tests.
- Add a supported Docker Compose path for API plus frontend.
- Add migration rollback and backup/restore checks for SQLite.
- Add stress reports for synthetic 100, 1,000, and 10,000 node ecosystems.
- Add graph/timeline/replay filtering for large datasets.
- Add a short demo script and screenshots for GitHub/social launch surfaces.

Exit criteria:

- V1.0 readiness score is at least 7.5/10.
- Integration examples are reproducible without hidden local state.
- API payload sizes are bounded or paginated.
- A new contributor can run tests and a browser smoke locally.

## Phase 3 - V1.0 Stable Candidate

Goal: make OpenMesh credible as a stable local/self-hosted observability tool.

Priority: P1.

Work items:

- Define a supported single-node deployment profile.
- Document database backup, retention, and migration procedures.
- Add release automation for wheel build, artifact inspection, tag validation,
  and GitHub prerelease/release publication.
- Add compatibility tests for protocol and registry versions.
- Add plugin packaging documentation and validation fixtures.
- Add read-only API auth option for self-hosted deployments.
- Add operational dashboards for ingestion rate, graph reduction time, replay
  generation time, and query latency.

Exit criteria:

- V1.0 readiness score is at least 8.5/10.
- Fresh install, self-hosted install, and package install paths are all
  documented and validated.
- CI covers backend, frontend, browser smoke, packaging, and release checks.

## Phase 4 - Cloud Foundation

Goal: make OpenMesh usable by teams without managing local infrastructure.

Priority: P2.

Future work:

- Hosted OpenMesh deployment.
- Multi-user organizations.
- Team workspaces.
- Hosted event storage.
- Shared observability dashboards.
- Workspace-level data retention controls.

Do not start this phase until the local/self-hosted V1 path is stable.

## Phase 5 - Ecosystem Integrations

Goal: connect OpenMesh to the broader observability and agent tooling ecosystem.

Priority: P1/P2.

Future work:

- LangSmith integration.
- OpenTelemetry collector interoperability hardening.
- Datadog export hardening.
- Grafana Tempo export hardening.
- Prometheus export hardening.
- Additional framework plugins after the plugin architecture is stable.

Rule: integrations must use the SDK/protocol/collector path and must not bypass
the OpenMesh graph reducer.

## Phase 6 - Enterprise Features

Goal: make OpenMesh suitable for organizational governance.

Priority: P2.

Future work:

- RBAC.
- SSO.
- Audit logs.
- Compliance reporting.
- Team governance.
- Workspace access policies.

Do not prioritize this before payload scaling, browser smoke, and deployment
basics are solved.

## Phase 7 - Agent Network

Goal: make observed agent ecosystems portable and shareable.

Priority: P2.

Future work:

- Public agent registry.
- Public workflow registry.
- Community-shared observability packs.
- Agent reputation network.
- Shared integration packs.

This phase should build on proven reputation, genome, workflow, and ecosystem
registry data rather than inventing separate social primitives.

## Deferred Until The Data Layer Is Boring

These are valuable, but should wait until trace/graph/replay/query paths are
fast, tested, and predictable:

- AI-generated root-cause analysis.
- Security posture scoring.
- Permission and trust-chain analysis.
- Live MCP capability execution.
- Automated remediation.
- Hosted multi-tenant governance.

## Success Metrics

V1 Alpha stabilization:

- Fresh clone to graph remains under five minutes.
- CI is green on every release-prep commit.
- Browser smoke has zero console errors on public routes.
- At least 10 external users can run `openmesh simulate` and see graph output.

V1 Beta:

- 1,000-node synthetic ecosystem stays responsive in CLI/API.
- Graph and timeline endpoints are paginated or windowed.
- At least three real-world integration examples are reproducible.
- Docs have one clear start path and one clear contributor path.

V1.0:

- Stable package install.
- Stable self-hosted install.
- Reliable migration path.
- Tested export path.
- Clear compatibility policy.
- Public users can understand, run, and extend OpenMesh without maintainer help.

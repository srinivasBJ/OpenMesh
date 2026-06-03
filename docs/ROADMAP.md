# OpenMesh Roadmap

## Now

- Prepare the v0.1 release package and documentation.
- Keep API, dashboard, CLI, and TUI reading from shared query services.
- Keep LangGraph and CrewAI integration plugins SDK-backed and observable through the existing collector path.
- Keep tests focused on protocol, trace, graph, discovery, diagnostics, SDK, and integration behavior.
- Keep ecosystem snapshots derived from existing reducers rather than introducing a parallel graph or registry model.
- Keep snapshot diffs derived from persisted snapshot payloads rather than introducing a second graph or registry model.
- Keep timelines derived from existing events, sessions, snapshots, diffs, graph state, traces, and provenance.
- Keep replays derived from timeline and snapshot payloads rather than introducing a second timeline or graph model.
- Keep structured queries derived from graph, discovery, provenance, trace, session, timeline, and snapshot read models.
- Keep federation metadata-only and derived from protocol, graph, snapshot, timeline, and replay read models.
- Keep evaluation measurement-only until baseline costs are understood.

## Next

- Publish the Python package after clean wheel and TestPyPI validation.
- Add richer process observation metadata such as working directory, duration, and environment hints.
- Add trace/session filtering to CLI commands.
- Add snapshot export formats after the persisted snapshot and diff payloads stabilize.
- Add timeline filtering after the core historical read model stabilizes.
- Add replay filtering and richer TUI playback controls after the stateless replay read model stabilizes.
- Add query filters, aliases, and saved-query management after the structured query grammar stabilizes.
- Add federation import/export and signed metadata exchange after metadata-only federation stabilizes.
- Establish performance baselines from synthetic 100, 1,000, and 10,000 node ecosystem evaluations.
- Add API tests around OpenMesh routes.
- Add release automation for package build, artifact inspection, and smoke tests.

## Later

- Add AutoGen, OpenHands, and Claude Code integration plugins after v0.1 stabilizes.
- Improve terminal UI inspection depth after the plain CLI workflows are reliable.
- Explore Active Analysis and MCP intelligence as a future layer:
  - MCP endpoint health checks
  - Live capability discovery
  - Tool inventory generation from live endpoints
  - Authentication analysis
  - Permission visibility
  - Dependency and trust-chain mapping
  - Security posture insights

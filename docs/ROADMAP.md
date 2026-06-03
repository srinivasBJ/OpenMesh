# OpenMesh Roadmap

## Now

- Prepare the v0.1 release package and documentation.
- Keep API, dashboard, CLI, and TUI reading from shared query services.
- Keep LangGraph and CrewAI integrations SDK-backed and observable through the existing collector path.
- Keep tests focused on protocol, trace, graph, discovery, diagnostics, SDK, and integration behavior.
- Keep ecosystem snapshots derived from existing reducers rather than introducing a parallel graph or registry model.

## Next

- Publish the Python package after clean wheel and TestPyPI validation.
- Add richer process observation metadata such as working directory, duration, and environment hints.
- Add trace/session filtering to CLI commands.
- Add snapshot export formats after the persisted snapshot payload stabilizes.
- Add API tests around OpenMesh routes.
- Add release automation for package build, artifact inspection, and smoke tests.

## Later

- Add AutoGen and OpenHands integrations after v0.1 stabilizes.
- Improve terminal UI inspection depth after the plain CLI workflows are reliable.
- Explore Active Analysis and MCP intelligence as a future layer:
  - MCP endpoint health checks
  - Live capability discovery
  - Tool inventory generation from live endpoints
  - Authentication analysis
  - Permission visibility
  - Dependency and trust-chain mapping
  - Security posture insights

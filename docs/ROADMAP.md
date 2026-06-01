# OpenMesh Roadmap

## Now

- Stabilize collector validation and persistence.
- Keep API, dashboard, and CLI reading from shared query services.
- Make local development work without Docker through SQLite mode.
- Add tests around the protocol core.
- Keep the LangGraph reference integration small, SDK-backed, and observable through existing CLI/TUI/API consumers.

## Next

- Package the CLI as a console script named `openmesh`.
- Add richer process observation metadata such as working directory, duration, and environment hints.
- Add trace/session filtering to CLI commands.
- Add API tests around OpenMesh routes.
- Add integration registry surfaces to CLI/API after the SDK registry shape settles.

## Later

- Harden Python SDK packaging and configuration.
- Add CrewAI, AutoGen, and OpenHands integrations after LangGraph proves the reference pattern.
- Improve terminal UI after the plain CLI workflows are reliable.
- Explore Active Analysis & MCP Discovery as a future layer:
  - MCP endpoint health checks
  - Capability discovery
  - Tool inventory generation
  - Authentication analysis
  - Permission visibility
  - Dependency and trust-chain mapping
  - Security posture insights

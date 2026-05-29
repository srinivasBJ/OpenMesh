# OpenMesh Vision

OpenMesh exists to make AI agent systems observable from the developer workflow, especially the terminal.

The project is not trying to be another log dashboard. The important object is the live network of agents, tools, commands, processes, traces, and sessions that produce AI work.

Current focus:

- Capture protocol-native OpenMesh events.
- Persist those events.
- Reconstruct traces from shared `trace_id` values.
- Derive graph state from stored events.
- Expose the same data through API, dashboard, and CLI consumers.
- Observe real command execution through `openmesh run -- <command>`.

The dashboard remains useful as a visualization layer, but the core product direction is protocol-first and CLI-consumable.

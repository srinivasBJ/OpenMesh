# OpenMesh Runtime Observability

OpenMesh can discover local coding-agent runtimes and record runtime activity as
normal OpenMesh protocol events.

Supported runtimes:

- Claude Code
- Codex CLI
- OpenCode
- Aider
- Cursor

This phase is metadata and observability only. OpenMesh does not remote-control
agents, execute editor actions, or inspect private agent internals.

## Discover Runtimes

```bash
openmesh runtimes discover
```

Example:

```text
OpenMesh Agent Runtimes

Claude Code  ✓ /usr/local/bin/claude
Codex CLI    ✓ /usr/local/bin/codex
OpenCode     ✓ /usr/local/bin/opencode
Aider        ✗ missing
Cursor       ✓ /Applications/Cursor.app
```

Runtime discovery checks local commands and known application locations. Missing
runtimes are reported without failing the local OpenMesh install.

## Observe a Runtime

```bash
openmesh observe codex
openmesh observe claude
```

Aliases are accepted:

- `claude`, `claude-code`
- `codex`, `codex-cli`
- `opencode`
- `aider`
- `cursor`

The command creates a session and trace, then emits runtime events through the
existing collector pipeline.

## Event Flow

Runtime observation emits:

```text
runtime.started
file.read
file.write
command.executed
tool.called
model.request
model.response
runtime.stopped
```

These events are persisted through `OpenMeshCollector.accept()` and appear in:

- `openmesh events`
- `openmesh traces`
- `openmesh graph --details`
- `openmesh timeline`
- `openmesh discover`
- `openmesh tui`
- the frontend Graph and Observatory pages

## Graph Relationships

Runtime events reduce into governed graph relationships:

```text
Codex CLI Agent
├─ uses -> Codex CLI model
├─ uses -> Codex CLI
├─ reads -> OpenMesh workspace
├─ writes -> OpenMesh workspace
└─ executes -> /usr/local/bin/codex
```

Each edge carries provenance:

- event ids
- trace ids
- session ids
- first seen / last seen timestamps
- observation count

## Observatory Metrics

The Observatory derives runtime metrics from persisted events and runtime
discovery:

- active runtimes
- detected runtimes
- commands executed
- files modified
- model requests
- runtime uptime

These are operational counters, not analysis or recommendations.

## Safety Boundaries

OpenMesh runtime observability is intentionally passive in this phase:

- no remote execution
- no remote control
- no credential capture
- no file content indexing
- no security analysis

Future runtime wrappers can add deeper process observation, but they should still
emit protocol events through the collector.

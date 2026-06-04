# Contributing To OpenMesh

OpenMesh is in v1.0 alpha hardening. Contributions are most valuable when they
make the product easier to install, validate, observe, and understand.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0

openmesh doctor
openmesh simulate --agents 8 --events 100
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Before A Pull Request

Run:

```bash
ruff check .
ruff format --check .
python -m compileall backend/src
python -m unittest discover -s backend/tests
cd frontend && npm run build
```

## Contribution Guidelines

- Preserve the single event pipeline.
- Do not add alternate graph, replay, timeline, or registry storage.
- Prefer SQLite-first local workflows.
- Keep optional integrations optional.
- Update docs when commands, setup, API routes, or behavior change.
- Add tests for collector, persistence, graph, trace, replay, diagnostics, or CLI
  changes.
- Keep frontend changes accessible and avoid blank pages.

## Good First Areas

- Documentation and examples.
- CLI help text and error messages.
- Tests around existing commands.
- Frontend empty states and route resilience.
- Packaging and install validation.

Community behavior is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

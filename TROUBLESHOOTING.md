# OpenMesh Troubleshooting

Use this guide when a fresh OpenMesh install does not behave like the quick
start.

## `openmesh: command not found`

Cause: the virtual environment where OpenMesh was installed is not active.

Fix:

```bash
source .venv/bin/activate
python -m pip install -e .
openmesh --help
```

## Python Or Dependency Install Fails

Cause: this release supports Python 3.11, 3.12, and 3.13. Python 3.14 is not
supported yet because pinned database dependencies do not install cleanly there.

Fix:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## `openmesh doctor` Reports Missing Tables

Expected first-user behavior: `openmesh doctor` bootstraps missing local tables
and finishes with `Overall: OK`.

Fix:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
openmesh doctor
```
If it still fails, remove the local database and retry:

```bash
rm -f ./openmesh.db
openmesh doctor
```

For Postgres, verify `DATABASE_URL`, server availability, and credentials.

## SDK Example Fails With `no such table: openmesh_events`

Cause: older checkouts required a CLI or backend command to create schema before
SDK examples emitted events.

Fix:

```bash
git pull
python -m pip install -e .
python examples/python_basic_agent.py
```

The SDK now bootstraps the event store before its first persisted event.

## LangGraph Example Says LangGraph Is Not Installed

Cause: LangGraph is an optional dependency.

Fix:

```bash
python -m pip install langgraph
python examples/langgraph_basic.py
```

## `openmesh doctor` Shows Optional Integrations As `Not installed`

This is not a failure. It means OpenMesh knows about the integration plugin, but
the external framework package is not installed in the current environment.

Install only the frameworks you want to run.

## Frontend Install Reports npm Vulnerabilities

`npm install` currently reports moderate/high dependency audit findings. This is
a release warning, not a startup blocker. The dashboard still installs, starts,
and builds in the validated local flow.

## Backend Starts But Shows `OpenMeshAI` In Health Output

Some legacy OpenMeshAI naming remains in active dashboard and simulation code.
This is not a startup blocker, but it is a product cleanup item.

## Duplicate `* 2.py` Or `* 2.sql` Files Appear Locally

These files are not part of a clean clone unless they are present in your local
working tree. Do not delete them blindly if you are carrying local work.

See [INSTALLATION_AUDIT.md](INSTALLATION_AUDIT.md) for the current duplicate
file classification.

## Reset Local SQLite State

Use this when you want to return to a blank local OpenMesh database:

```bash
rm -f ./openmesh.db
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
openmesh doctor
```

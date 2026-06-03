# OpenMesh Installation

OpenMesh can be installed as a Python package for local development and CLI use.

## Editable Install

From the repository root:

```bash
python -m pip install -e .
```

This installs:

- the public Python SDK import:

```python
from openmesh import OpenMeshClient
```

- the CLI command:

```bash
openmesh doctor
openmesh discover
openmesh ecosystem
openmesh graph
openmesh trace <trace_id>
openmesh workflows
openmesh capabilities
openmesh integrations
openmesh tui
```

## Local SQLite Mode

OpenMesh defaults to SQLite in development when `aiosqlite` is installed.

Optional explicit configuration:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
```

Initialize local tables by starting the backend once:

```bash
uvicorn src.main:app --reload --port 8000
```

For command-only validation, the CLI can still report missing tables through:

```bash
openmesh doctor
```

## Package Install

When published to PyPI:

```bash
python -m pip install openmesh
```

Then validate:

```bash
openmesh doctor
openmesh discover
openmesh ecosystem
openmesh graph
openmesh tui --once
```

## Validation Commands

From a fresh environment:

```bash
python -m pip install -e .
openmesh doctor
openmesh discover
openmesh ecosystem
openmesh integrations
openmesh tui --once
python -c "from openmesh import OpenMeshClient; print(OpenMeshClient.__name__)"
```

Expected result:

- `openmesh` resolves as a console command.
- `openmesh doctor` can reach the configured database or reports clear diagnostics.
- `openmesh discover` and `openmesh ecosystem` render terminal inventories.
- `openmesh tui --once` prints a terminal capture.
- `from openmesh import OpenMeshClient` imports successfully.

## Examples

Run examples from the repository root after installing OpenMesh:

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
python examples/crewai_basic.py
```

The LangGraph example requires LangGraph:

```bash
python -m pip install langgraph
python examples/langgraph_basic.py
```

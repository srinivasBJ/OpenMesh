# OpenMesh Release Checklist

Use this checklist before publishing an OpenMesh Python package release.

Use Python 3.11 for release validation. OpenMesh v0.1 declares `requires-python = ">=3.11"`, but dependency wheels should be verified on the supported release target before publishing.

## Package Metadata

- [ ] `pyproject.toml` version is updated.
- [ ] `README.md` describes install and CLI usage.
- [ ] License metadata matches `LICENSE`.
- [ ] Installable command launcher `scripts/openmesh` is included.
- [ ] Public SDK import works:

```bash
python -c "from openmesh import OpenMeshClient; print(OpenMeshClient.__name__)"
```

## Local Validation

Run from repository root:

```bash
python -m pip install -e .
openmesh doctor
openmesh discover
openmesh ecosystem
openmesh graph
openmesh integrations
openmesh tui --once
```

Example checks:

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
python examples/crewai_basic.py
python examples/langgraph_basic.py
```

Backend checks:

```bash
cd backend
python -m compileall src tests
python -m unittest discover -s tests
```

Frontend check:

```bash
cd frontend
npm run build
```

## Build Validation

Build package artifacts:

```bash
python -m build
```

Inspect package contents:

```bash
python -m tarfile -l dist/openmesh-*.tar.gz
python -m zipfile -l dist/openmesh-*.whl
```

Install wheel in a clean virtual environment:

```bash
python3.11 -m venv /tmp/openmesh-release-venv
/tmp/openmesh-release-venv/bin/python -m pip install dist/openmesh-*.whl
/tmp/openmesh-release-venv/bin/openmesh doctor
```

## Publish

TestPyPI first:

```bash
python -m pip install build twine
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*
python -m twine upload --repository testpypi dist/*
```

Validate TestPyPI from a clean virtual environment:

```bash
python3.11 -m venv /tmp/openmesh-testpypi
/tmp/openmesh-testpypi/bin/python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple openmesh
OPENMESH_SQLITE_PATH=/tmp/openmesh-testpypi.db /tmp/openmesh-testpypi/bin/python -c "import asyncio; from src.db.session import init_db; asyncio.run(init_db())"
OPENMESH_SQLITE_PATH=/tmp/openmesh-testpypi.db /tmp/openmesh-testpypi/bin/openmesh doctor
OPENMESH_SQLITE_PATH=/tmp/openmesh-testpypi.db /tmp/openmesh-testpypi/bin/openmesh discover
OPENMESH_SQLITE_PATH=/tmp/openmesh-testpypi.db /tmp/openmesh-testpypi/bin/openmesh ecosystem
```

PyPI:

```bash
python -m twine upload dist/*
```

## Post-Release

- [ ] Verify `pip install openmesh` in a clean environment.
- [ ] Verify `openmesh doctor`.
- [ ] Verify `openmesh discover`.
- [ ] Verify `openmesh ecosystem`.
- [ ] Verify `openmesh graph`.
- [ ] Verify `openmesh trace <trace_id>`.
- [ ] Verify `openmesh workflows`.
- [ ] Verify `openmesh capabilities`.
- [ ] Verify `openmesh integrations`.
- [ ] Verify `openmesh tui --once`.
- [ ] Verify SDK, async SDK, LangGraph, and CrewAI examples.
- [ ] Tag the release in Git.
- [ ] Update release notes.

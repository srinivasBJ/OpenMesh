# OpenMesh Release Hardening

This document tracks readiness for the first public GitHub release.

Scope:

- No new features.
- No new integrations.
- No MCP execution, MCP health checks, or MCP analysis.
- Release quality, documentation, packaging, and validation only.

## GitHub-Facing Documentation Reviewed

- `README.md`
- `docs/INSTALLATION.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/OPENMESH_V0_1_RELEASE.md`
- `docs/ROADMAP.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/DOCTOR.md`
- `docs/integrations/LANGGRAPH.md`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/*.md`

## README Onboarding Review

The README now points users through:

1. Backend configuration.
2. Optional Docker services.
3. Backend startup.
4. Frontend startup.
5. Editable package install.
6. Installed `openmesh` CLI usage.
7. SDK and integration examples.

The onboarding flow is acceptable for an alpha public release. The main warning is that the README still carries older OpenMeshAI dashboard and simulation language alongside the newer terminal-first OpenMesh protocol direction. That is acceptable for v0.1 if the release notes frame the dashboard as a visualization layer.

## Documented Command Validation

Validated locally against SQLite:

- `openmesh doctor`
- `openmesh discover`
- `openmesh ecosystem`
- `openmesh graph --details`
- `openmesh traces`
- `openmesh trace <trace_id>`
- `openmesh workflows`
- `openmesh capabilities`
- `openmesh integrations`
- `openmesh tui --once`

Documented example scripts validated locally:

- `python examples/python_basic_agent.py`
- `python examples/python_async_agent.py`
- `python examples/langgraph_basic.py`
- `python examples/crewai_basic.py`

## GitHub Actions Release Validation

The CI workflow includes a release-validation job that:

- Installs OpenMesh with `python -m pip install -e .`.
- Initializes a SQLite database.
- Runs:
  - `openmesh doctor`
  - `openmesh discover`
  - `openmesh ecosystem`
- Builds a wheel.
- Installs the wheel into a clean virtual environment.
- Runs the same installed CLI smoke checks from the wheel environment.

## Wheel-Install Smoke Tests

Expected local release smoke sequence:

```bash
python -m pip install build
python -m build --wheel
python3.11 -m venv /tmp/openmesh-wheel-smoke
/tmp/openmesh-wheel-smoke/bin/python -m pip install dist/openmesh-*.whl
OPENMESH_SQLITE_PATH=/tmp/openmesh-wheel-smoke.db /tmp/openmesh-wheel-smoke/bin/python -c "import asyncio; from src.db.session import init_db; asyncio.run(init_db())"
OPENMESH_SQLITE_PATH=/tmp/openmesh-wheel-smoke.db /tmp/openmesh-wheel-smoke/bin/openmesh doctor
OPENMESH_SQLITE_PATH=/tmp/openmesh-wheel-smoke.db /tmp/openmesh-wheel-smoke/bin/openmesh discover
OPENMESH_SQLITE_PATH=/tmp/openmesh-wheel-smoke.db /tmp/openmesh-wheel-smoke/bin/openmesh ecosystem
```

## TestPyPI Checklist

Before publishing to PyPI:

```bash
python -m pip install build twine
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*
python -m twine upload --repository testpypi dist/*
```

Validate from TestPyPI:

```bash
python3.11 -m venv /tmp/openmesh-testpypi
/tmp/openmesh-testpypi/bin/python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple openmesh
OPENMESH_SQLITE_PATH=/tmp/openmesh-testpypi.db /tmp/openmesh-testpypi/bin/python -c "import asyncio; from src.db.session import init_db; asyncio.run(init_db())"
OPENMESH_SQLITE_PATH=/tmp/openmesh-testpypi.db /tmp/openmesh-testpypi/bin/openmesh doctor
OPENMESH_SQLITE_PATH=/tmp/openmesh-testpypi.db /tmp/openmesh-testpypi/bin/openmesh discover
OPENMESH_SQLITE_PATH=/tmp/openmesh-testpypi.db /tmp/openmesh-testpypi/bin/openmesh ecosystem
```

## Release Blockers

- TestPyPI validation has not been completed yet.
- Final GitHub Actions release-validation job must pass on GitHub, not only locally.
- The repository still contains untracked duplicate local artifacts in this working copy; decide whether to remove, ignore, or leave them out before tagging.

## Release Warnings

- `openmesh doctor` can report ecosystem duplicate-name issues when all examples are run into the same database because multiple integrations intentionally use names such as `Research Agent` and `web_search`.
- The LangGraph example currently lacks workflow `source` metadata, which strict workflow diagnostics report.
- The README still includes legacy dashboard/simulation language. The v0.1 release notes clarify that the dashboard is a visualization layer, not the core product.
- The package is alpha-quality and integration APIs should not be treated as stable.
- SQLite is suitable for local validation, but production behavior should be validated with Postgres before serious deployment.
- Release smoke tests should use Python 3.11. Newer local interpreters may force source builds for pinned dependencies that already have wheels on Python 3.11.

## Release Readiness Score

**8.3 / 10**

The repository is ready for a first public GitHub alpha release after CI passes and TestPyPI installation is verified.

## Recommended Tag Version

`v0.1.0`

Rationale:

- The package metadata already declares `0.1.0`.
- The release is the first protocol, CLI, TUI, SDK, and reference-integration milestone.
- The API is alpha and should use a `0.x` semantic version.

## Recommended v0.2 Priorities

- Clean-environment CI for more CLI commands and examples.
- Normalize example metadata so `openmesh doctor` is clean after running all examples together.
- Add API route tests for OpenMesh protocol endpoints.
- Improve TUI inspection for traces, nodes, and relationships.
- Harden package metadata, dependency bounds, and platform-specific install behavior.
- Keep MCP execution, security analysis, and root-cause analysis out of scope until the observability layer is stable.

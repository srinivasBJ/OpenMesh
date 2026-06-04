# OpenMesh v1 Alpha Repository Audit

Date: 2026-06-04

## KEEP

- `backend/src`: active backend, CLI, TUI, SDK, services, providers, runtimes,
  MCP, replay, failures, reputation, genome, exporters, workflows.
- `frontend/src`: active React dashboard and graph visualization.
- `docs/protocol`: OpenMesh Protocol v1 documentation and JSON Schemas.
- `examples`: runnable SDK and showcase examples, with optional dependency
  caveats.
- `.github/workflows/ci.yml`: active CI.
- `.github/ISSUE_TEMPLATE`: useful public project scaffolding.
- `openmesh/` and `scripts/openmesh`: package and CLI entrypoint compatibility.
- `shared/types/openmesh_event.schema.json`: shared protocol schema artifact.

## MOVE

- Root release/audit docs such as `INSTALLATION_AUDIT.md`,
  `PUBLIC_RELEASE_CHECKLIST.md`, `STARTUP_GUIDE.md`, and `TROUBLESHOOTING.md`
  could eventually move under `docs/` for a cleaner root.
- `ROADMAP.md` and `DECISIONS.md` exist in root and docs. Keep for now, but
  merge later into canonical `docs/ROADMAP.md` and `docs/DECISIONS.md`.

## MERGE

- `ARCHITECTURE.md` and `docs/ARCHITECTURE.md`: root should stay concise;
  `docs/SYSTEM_ARCHITECTURE.md` should become the canonical long-form inventory.
- `docs/ARCHITECTURE_AUDIT.md` and `docs/INTEGRATION_AUDIT.md`: related but
  distinct; merge only when preparing a final release package.
- Integration docs in `docs/integrations/` should eventually share one template.

## DELETE CANDIDATES

Do not delete automatically without maintainer review.

- `.DS_Store` files in root, `.github`, `backend`, `docs`, `frontend`, `shared`,
  and ignored build/cache folders.
- Ignored local build artifacts:
  - `build/`
  - `.ruff_cache/`
  - `openmesh.egg-info/`
  - local `openmesh.db`
  - local `backend/openmesh.db`
- Accidental Git internals artifact:
  - `.git/index 2`
- Empty accidental directories:
  - `{backend,frontend}`
  - `backend/{src`

## Duplicate Artifact Scan

No tracked duplicate files ending in these patterns were found during this pass:

- `* 2.py`
- `* 2.sql`
- `* 2.md`
- `* 3.py`

## Release Hygiene Risks

- Root contains several historical planning docs. They are useful, but the root
  can feel crowded for first users.
- Local ignored artifacts should be removed before creating release archives.
- The project name has mostly moved to OpenMesh, but old OpenMeshAI wording may
  still exist in historical docs and GitHub URLs.

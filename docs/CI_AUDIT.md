# OpenMesh v1 Alpha CI Audit

Date: 2026-06-04

## GitHub Actions State Reviewed

Workflow reviewed: `AgentVerse CI`

Release hardening change: renamed workflow to `OpenMesh CI`.

Latest failed run:

- Run: `26944821295`
- Commit: `3c14a7545f76ecdc9bb694165006c9d809491012`
- URL: `https://github.com/srinivasBJ/OpenMesh/actions/runs/26944821295`

Jobs:

- `backend`: success
- `frontend`: success
- `release-validation`: failure

## Failure Classification

### release-validation / Validate wheel install

Classification: real product issue

Failure:

```text
ModuleNotFoundError: No module named 'src.exporters'
```

Cause:

`pyproject.toml` used a manual setuptools package list. Newer backend packages
were present in source but missing from wheel metadata:

- `src.exporters`
- `src.failures`
- `src.genome`
- `src.reputation`

Impact:

Editable installs worked locally, but wheel installs failed when invoking the
installed `openmesh` CLI. This blocks public release.

Fix:

Added the missing packages to `pyproject.toml`.

Local validation:

- Built wheel from `/tmp` to avoid the ignored repository `build/` directory
  shadowing the PyPI `build` module.
- Installed wheel into `/tmp/openmesh-wheel-v1-smoke`.
- Ran:
  - `openmesh doctor`
  - `openmesh discover`
  - `openmesh ecosystem`

Result: PASS.

## Packaging Warnings

Initial local wheel smoke emitted setuptools warnings for license metadata and
`src.db.migrations`. These were cleaned up by:

- changing `project.license` to the SPDX string `MIT`
- removing the deprecated license classifier
- adding `src.db.migrations` to package metadata

Local wheel build now completes without those warnings.

## CI Recommendations

- Keep wheel install smoke in CI.
- Add backend tests to CI after public launch if runtime remains acceptable.
- Add a browser route smoke job only after a browser runner is intentionally
  added.

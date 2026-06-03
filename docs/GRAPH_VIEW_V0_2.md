# OpenMesh Graph View v0.2

OpenMesh Graph View is the browser visualization layer for the existing
OpenMesh graph APIs. It does not introduce new storage, registries, event
types, or graph models.

## Route

```text
/graph
```

The page uses existing API routes:

- `GET /api/openmesh/graph`
- `GET /api/openmesh/traces`
- `GET /api/openmesh/traces/{trace_id}`
- `GET /api/openmesh/inspect/{node_id}`
- `GET /api/openmesh/timeline`
- `GET /api/openmesh/timeline/trace/{trace_id}`
- `GET /api/openmesh/ecosystem`

## Capabilities

- SVG graph rendering
- zoom and pan
- node selection
- relationship selection
- node inspector
- relationship inspector
- entity type filters
- relationship type filters
- lifecycle filters
- neighborhood depth controls
- search
- trace selection and graph highlighting
- graph evolution panel
- empty-state onboarding with first-run commands

## Data Flow

```text
OpenMesh APIs
  -> frontend API client
  -> graph controls and filters
  -> SVG graph layout
  -> inspector and timeline panels
```

The frontend derives visible graph state from the reducer output already
returned by `/api/openmesh/graph`. Node inspection and trace timeline details
come from their existing read APIs.

## Local Validation

When another service already owns port 8000, run the frontend with a custom
proxy target:

```bash
OPENMESH_SQLITE_PATH=/tmp/openmesh-graph-view.db \
  python -m uvicorn src.main:app --host 127.0.0.1 --port 8010

VITE_API_PROXY_TARGET=http://127.0.0.1:8010 \
  npm run dev -- --host 127.0.0.1 --port 5174
```

Then open:

```text
http://127.0.0.1:5174/graph
```

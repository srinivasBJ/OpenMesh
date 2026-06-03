# OpenMesh Federation

OpenMesh federation lets multiple OpenMesh instances exchange ecosystem
metadata. It is designed for multiple machines, organizations, agent clusters,
and OpenMesh deployments.

Federation is metadata only.

It does not provide:

- remote execution
- remote control
- code execution
- security analysis
- health checks
- recommendations

## Commands

```bash
openmesh federation
openmesh federation list
openmesh federation inspect
openmesh federation inspect federation:remote-a
openmesh federation peers
```

## Configuration

Peers are configured with `OPENMESH_FEDERATION_PEERS`.

JSON form:

```bash
export OPENMESH_FEDERATION_PEERS='[
  {
    "instance_id": "remote-a",
    "name": "Remote A",
    "organization": "research",
    "cluster": "agents",
    "endpoint": "https://remote-a.example/openmesh"
  }
]'
```

Comma-separated endpoint form:

```bash
export OPENMESH_FEDERATION_PEERS="https://one.example,https://two.example"
```

Local node metadata can be configured with:

- `OPENMESH_INSTANCE_ID`
- `OPENMESH_INSTANCE_NAME`
- `OPENMESH_ORGANIZATION`
- `OPENMESH_CLUSTER`
- `OPENMESH_FEDERATION_ENDPOINT`

## Model

Federation introduces a governed node type:

```text
federation_node
```

Federation introduces a governed relationship type:

```text
federation_node -> federates_with -> federation_node
```

Federation relationships include provenance metadata, but they do not require
remote event ingestion. Configured peer metadata is enough to create the local
federation registry view.

## Read Models

Federation reuses existing OpenMesh read models:

```text
protocol v1
  -> graph model
  -> snapshot model
  -> timeline model
  -> replay model
  -> federation registry
```

Federation registry output includes:

- local federation node
- peer federation nodes
- federation relationships
- federation discovery metadata
- federation query catalog
- federation snapshot
- federation timeline
- federation replay

## API

```bash
GET /api/openmesh/federation
GET /api/openmesh/federation/peers
GET /api/openmesh/federation/inspect/{node_id}
```

## Policy

Every federation payload includes:

```json
{
  "metadata_only": true,
  "remote_execution": false,
  "remote_control": false,
  "code_execution": false,
  "security_analysis": false
}
```

This is intentional. Federation is an ecosystem mapping and metadata exchange
foundation, not a remote operations layer.

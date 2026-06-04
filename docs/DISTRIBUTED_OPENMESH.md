# Distributed OpenMesh

Distributed OpenMesh lets multiple installations contribute events to one shared ecosystem graph. It does not add a second graph model or a new storage path. Each node emits normal OpenMesh events through the collector, and graph relationships are reduced from those persisted events.

## Node Identity

Each installation has a local identity stored at:

```bash
~/.openmesh/node.json
```

Supported identity fields:

- `node_id`
- `node_name`
- `node_type`

Supported `node_type` values:

- `laptop`
- `workstation`
- `server`
- `cloud`

Environment overrides:

```bash
OPENMESH_NODE_ID=my-laptop
OPENMESH_NODE_NAME="Srinivas Laptop"
OPENMESH_NODE_TYPE=laptop
OPENMESH_NODE_CONFIG=/custom/node.json
```

## Events

Distributed nodes use the existing OpenMesh event envelope.

New event types:

- `node.joined`
- `node.left`
- `node.heartbeat`

`node.heartbeat` can carry a governed `hosts` relationship when it includes a target entity.

## Relationships

New governed relationship:

```text
openmesh_node -> hosts -> agent
openmesh_node -> hosts -> runtime
openmesh_node -> hosts -> mcp_server
```

These relationships include normal OpenMesh provenance:

- event ids
- trace ids
- session ids
- first seen
- last seen
- observation count

## Commands

Register the local installation:

```bash
openmesh node register --name "Developer Laptop" --type laptop
```

Show local identity and registry status:

```bash
openmesh node status
```

List observed OpenMesh nodes:

```bash
openmesh node list
```

Generate a distributed demo ecosystem:

```bash
openmesh simulate --nodes 4
```

## APIs

List observed OpenMesh nodes:

```http
GET /api/openmesh/nodes
```

Show local node status:

```http
GET /api/openmesh/node/status
```

Ingest federated events:

```http
POST /api/openmesh/federation/events
```

Payload:

```json
{
  "events": [
    {
      "spec_version": "0.1",
      "event_id": "evt_example",
      "event_type": "node.heartbeat",
      "timestamp": "2026-06-04T00:00:00Z",
      "trace_id": "trace_example",
      "session_id": "sess_example",
      "source": {
        "node_id": "node_laptop",
        "node_type": "openmesh_node",
        "name": "Developer Laptop"
      },
      "payload": {
        "status": "active"
      }
    }
  ]
}
```

The endpoint validates and persists events through the collector. It does not perform remote execution or remote control.

## Observatory

The frontend Observatory displays:

- active nodes
- longest observed node uptime
- hosted agents
- hosted runtimes
- hosted MCP servers
- host relationship count

## Graph Behavior

Distributed nodes appear as governed `openmesh_node` graph nodes. Host edges appear as governed `hosts` relationships and can be inspected through the graph, CLI, API, and provenance views.

## Validation

Recommended local validation:

```bash
openmesh node status
openmesh node list
openmesh simulate --nodes 4
openmesh graph --details
openmesh doctor
python -m unittest discover -s backend/tests
npm run build
```

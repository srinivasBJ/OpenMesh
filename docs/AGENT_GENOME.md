# Agent Genome

OpenMesh Agent Genome creates behavioral DNA profiles for observed agents. It is a deterministic profile built from persisted OpenMesh events, not an AI summary.

## Tracked Traits

Each genome tracks:

- preferred models
- preferred tools
- preferred MCP servers
- average context size
- handoff patterns
- failure patterns
- cost profile
- latency profile

The genome also includes a stable `genome_signature` derived from the agent's observed tool, model, MCP, and failure traits.

## Similarity Relationships

OpenMesh compares agent genomes and emits governed graph relationships:

```text
Agent -> resembles -> Agent
```

Similarity considers:

- shared tools
- shared models
- shared MCP servers
- shared failure patterns
- shared handoff patterns
- latency similarity
- cost similarity

Similarity edges are emitted as normal OpenMesh events through the collector, so graph provenance can explain why two agents resemble each other.

## CLI

Inspect one agent genome:

```bash
openmesh genome "Planner Agent"
```

Compare two agents:

```bash
openmesh compare "Planner Agent" "Coder Agent"
```

## APIs

```http
GET /api/openmesh/genome
GET /api/openmesh/genome/{agent_id}
GET /api/openmesh/genome/compare?agent_a=Planner%20Agent&agent_b=Coder%20Agent
```

API reads are non-mutating by default. CLI genome commands persist newly observed `resembles` edges so graph views can show the similarity layer.

## Validation

Recommended validation:

```bash
openmesh genome <agent>
openmesh compare <agentA> <agentB>
openmesh graph --details
openmesh doctor
python -m unittest discover -s backend/tests
npm run build
```

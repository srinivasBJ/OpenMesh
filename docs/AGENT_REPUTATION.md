# Agent Reputation

OpenMesh Agent Reputation measures how agents perform over time using existing OpenMesh event history. It is deterministic infrastructure, not AI judgment.

## Metrics

Each agent receives six 0-100 metrics:

- `success_rate`
- `workflow_completion_rate`
- `tool_reliability`
- `handoff_quality`
- `response_latency`
- `cost_efficiency`

OpenMesh combines those into:

```text
agent_score
```

The score is weighted toward successful work, completed workflows, reliable tools, and high-quality handoffs. Latency and cost efficiency are included so fast, efficient agents surface above noisy or expensive ones.

## Trust Relationships

OpenMesh derives trust from observed collaboration evidence:

```text
Agent -> trusts -> Agent
```

Trust evidence includes:

- successful handoffs
- review handoffs
- agent messages
- failed handoffs as negative evidence

Trust edges are emitted as normal OpenMesh events through the collector, so graph provenance can answer why the edge exists.

## CLI

Rank observed agents:

```bash
openmesh rankings
```

Inspect one agent:

```bash
openmesh agent score agent:planner
```

Agent names also work when unique:

```bash
openmesh agent score "Planner Agent"
```

## APIs

```http
GET /api/openmesh/reputation
GET /api/openmesh/reputation/{agent_id}
```

API reads are non-mutating by default. CLI reputation commands persist newly observed trust edges so the graph can display the reputation layer.

## Observatory

The Observatory shows:

- Top Agents
- Top Reviewers
- Most Reliable Agents
- Fastest Agents
- average agent score
- trust relationship count

## Validation

Recommended validation:

```bash
openmesh rankings
openmesh agent score <agent_id>
openmesh graph --details
openmesh doctor
python -m unittest discover -s backend/tests
npm run build
```

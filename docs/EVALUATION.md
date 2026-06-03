# OpenMesh Evaluation

OpenMesh evaluation measures the cost of deriving ecosystem views from observed
OpenMesh state. It is a benchmark harness, not an optimization pass.

The framework generates deterministic synthetic ecosystems and runs them through
the existing collector, trace, graph, inspection, query, snapshot, timeline,
replay, and federation read models.

## Commands

Run the default benchmark suite:

```bash
openmesh evaluate
```

Run specific ecosystem sizes:

```bash
openmesh evaluate --sizes 100
openmesh evaluate --sizes 100 1000 10000
```

Write a machine-readable report:

```bash
openmesh evaluate --sizes 100 1000 10000 --json > openmesh-evaluation.json
```

Measure derived read models without collector ingestion:

```bash
openmesh evaluate --sizes 1000 --skip-ingestion
```

## Synthetic Ecosystems

The benchmark generator creates ecosystems with these node categories:

- agents
- tools
- workflows
- processes
- services
- MCP servers
- capabilities

Default benchmark sizes:

- 100 nodes
- 1,000 nodes
- 10,000 nodes

Each synthetic node emits an OpenMesh event with trace, session, span, and graph
relationship metadata. Events are converted to in-memory records so benchmarks
can exercise reducers without requiring a production database.

## Benchmarked Operations

The suite currently measures:

- event ingestion through `OpenMeshCollector.accept`
- trace reconstruction
- graph reduction
- node inspection
- query engine latency
- snapshot creation
- snapshot diff
- timeline generation
- replay generation
- federation aggregation

Federation benchmarks aggregate metadata only. They do not contact remote peers.

## Metrics

Each benchmark metric records:

- `elapsed_ms`: wall-clock execution time
- `peak_memory_bytes`: peak traced Python memory
- `peak_memory_mb`: human-readable peak memory
- `details`: operation-specific counts such as nodes, edges, traces, sessions,
  frames, or query latencies

The report also includes:

- synthetic node count
- synthetic event count
- trace count
- session count
- graph node count
- graph edge count

## Notes

The benchmark suite intentionally reuses existing OpenMesh services:

```text
synthetic events
  -> collector and event records
  -> trace reconstruction
  -> graph reducer
  -> inspection and query services
  -> snapshot, diff, timeline, replay, and federation views
```

No second graph model, storage model, or evaluation-only registry is introduced.
The goal is to establish reproducible baseline measurements before optimizing
any part of the system.

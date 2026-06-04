# OpenMesh CLI Reference

Generated for v1.0 alpha audit on 2026-06-04.

## Core Health

- `openmesh health`
- `openmesh doctor`

## Event, Trace, Session, Graph

- `openmesh events [--limit N]`
- `openmesh traces [--limit N]`
- `openmesh trace <trace_id>`
- `openmesh graph [--details]`
- `openmesh nodes`
- `openmesh inspect <node>`
- `openmesh registry`

## Discovery And Ecosystem

- `openmesh discover [--limit N]`
- `openmesh ecosystem [--limit N]`
- `openmesh integrations`
- `openmesh plugins list`
- `openmesh plugins inspect <plugin>`
- `openmesh plugins validate <plugin>`

## Snapshots, Timeline, Replay, Query

- `openmesh snapshot create`
- `openmesh snapshot list`
- `openmesh snapshot inspect <snapshot_id>`
- `openmesh snapshot diff <snapshot_a> <snapshot_b>`
- `openmesh timeline [--limit N]`
- `openmesh timeline node <node_id>`
- `openmesh timeline workflow <workflow_id>`
- `openmesh timeline trace <trace_id>`
- `openmesh replay ecosystem [--control step|previous|jump|start|pause|stop]`
- `openmesh replay snapshot <snapshot_id>`
- `openmesh replay trace <trace_id>`
- `openmesh replay workflow <workflow_id>`
- `openmesh query --saved`
- `openmesh query [--limit N] <structured query>`

Query examples:

- `openmesh query agents using web_search`
- `openmesh query workflows using search`
- `openmesh query relationships created since 2026-06-03T00:00:00Z`
- `openmesh query nodes added between snapshots`
- `openmesh query traces involving "Research Agent"`
- `openmesh query capabilities exposed by "Search MCP"`

Place `--limit` before query text.

## Providers And Models

- `openmesh providers verify`
- `openmesh providers discover`
- `openmesh models list`
- `openmesh run-demo research --provider <provider> [--model <model>]`

Cloud provider demos require API keys. Local provider demos require a running
Ollama, LM Studio, or vLLM server.

## Runtimes And Processes

- `openmesh runtimes discover`
- `openmesh observe codex`
- `openmesh observe claude`
- `openmesh run -- <command>`

## MCP, Tools, Capabilities, Workflows

- `openmesh mcp discover`
- `openmesh mcp`
- `openmesh mcp-config`
- `openmesh capabilities`
- `openmesh tools`
- `openmesh resources`
- `openmesh workflows`
- `openmesh workflow list`
- `openmesh workflow inspect <workflow_id>`
- `openmesh workflow replay <workflow_id>`
- `openmesh run-demo multi-agent [--agents N] [--handoffs N] [--messages N]`

## Failure, Reputation, Genome

- `openmesh failures`
- `openmesh failure inspect <failure_id>`
- `openmesh failure report`
- `openmesh rankings`
- `openmesh agent score <agent_id>`
- `openmesh genome <agent_id>`
- `openmesh compare <agent_a> <agent_b>`

## Distributed And Federation

- `openmesh node status`
- `openmesh node register`
- `openmesh node list`
- `openmesh federation list`
- `openmesh federation peers`
- `openmesh federation inspect <node_id>`

## Export

- `openmesh export otel [--summary|--output path|--endpoint url]`
- `openmesh export tempo [--summary|--output path|--endpoint url]`
- `openmesh export jaeger [--summary|--output path|--endpoint url]`
- `openmesh export datadog [--summary|--output path|--endpoint url] [--api-key key]`
- `openmesh export prometheus [--summary|--output path]`

## TUI And Evaluation

- `openmesh tui`
- `openmesh tui --once`
- `openmesh evaluate --sizes 100 1000`

## Simulation

- `openmesh simulate --agents 20 --events 500`
- `openmesh simulate --agents 20 --events 500 --nodes 4`
- `openmesh simulate --agents 12 --events 180 --seed 11`

# OpenMesh Local LLM Integration

OpenMesh can discover and observe local model runtimes as first-class ecosystem
entities.

Supported local providers:

- Ollama
- LM Studio
- vLLM

OpenMesh does not require API keys for local providers. It discovers providers
over localhost HTTP endpoints and emits normal OpenMesh events when a local
model is used.

## Default Endpoints

```bash
export OLLAMA_BASE_URL="http://localhost:11434"
export LMSTUDIO_BASE_URL="http://localhost:1234"
export VLLM_BASE_URL="http://localhost:8000"
```

Optional model defaults:

```bash
export OLLAMA_MODEL="hermes3"
export LMSTUDIO_MODEL="qwen3"
export VLLM_MODEL="deepseek-r1"
```

## Discover Providers

```bash
openmesh providers discover
```

Example:

```text
Local LLM Providers

Ollama      ✓ http://localhost:11434
LM Studio   ✓ http://localhost:1234
vLLM        ✗ http://localhost:8000
```

Unavailable providers are reported, not treated as fatal. This lets a local
operator see which runtimes are active without breaking the CLI.

## List Local Models

```bash
openmesh models list
```

Example:

```text
Local Models

hermes3                          Ollama     http://localhost:11434
qwen3                            LM Studio  http://localhost:1234
deepseek-r1                      vLLM       http://localhost:8000
```

## Run a Local Model Demo

```bash
openmesh run-demo research --provider ollama --model hermes3
```

Other examples:

```bash
openmesh run-demo research --provider lmstudio --model qwen3
openmesh run-demo research --provider vllm --model deepseek-r1
```

## Event Flow

Local provider calls emit:

```text
trace.started
model.loaded
llm.request
llm.response
tool.call.started
tool.call.completed
trace.completed
```

These events are persisted through `OpenMeshCollector.accept()` and become
visible in:

- `openmesh graph --details`
- `openmesh timeline`
- `openmesh discover`
- `openmesh ecosystem`
- `openmesh tui`
- the frontend Graph and Observatory pages

## Graph Relationships

OpenMesh represents local provider topology as governed graph relationships:

```text
LLM Research Agent
└─ uses -> hermes3

hermes3
└─ served_by -> Ollama
```

The `served_by` edge includes event ids, trace ids, timestamps, span ids, and
observation counts through graph provenance.

## Observatory Metrics

The Observatory reads local LLM metrics from persisted events and live provider
discovery:

- local latency
- tokens/sec
- provider uptime
- active model count

Metrics are operational signals only. OpenMesh does not run health analysis,
security analysis, or recommendations in this phase.

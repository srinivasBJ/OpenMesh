# OpenMesh LLM Integration

OpenMesh can observe real LLM provider activity through the same collector,
event store, trace reconstruction, graph reducer, timeline, and frontend views
used by simulator and SDK events.

This is Phase 1 provider support. It adds direct provider calls only. It does
not change simulator behavior and does not add a second event pipeline.

## Providers

Supported providers:

- OpenAI
- Anthropic
- OpenRouter

Configuration is environment-variable based:

```bash
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export OPENROUTER_API_KEY="..."
```

Optional model overrides:

```bash
export OPENAI_MODEL="gpt-4o-mini"
export ANTHROPIC_MODEL="claude-3-5-haiku-latest"
export OPENROUTER_MODEL="openai/gpt-4o-mini"
```

## Verify Providers

```bash
openmesh providers verify
```

When keys are present, OpenMesh checks provider connectivity:

```text
OpenMesh LLM Providers

✓ OpenAI models endpoint reachable
✓ Anthropic models endpoint reachable
✓ OpenRouter models endpoint reachable
```

When a key is missing, the provider is reported as not configured instead of
being treated as a broken local install:

```text
○ OpenAI OPENAI_API_KEY is not set
```

Use strict mode in CI or release validation when all providers must be present:

```bash
openmesh providers verify --strict
```

## Research Demo

Run a real provider-backed workflow:

```bash
openmesh run-demo research \
  --provider openai \
  --query "What should an AI agent observability graph reveal?"
```

Provider can be:

- `auto`
- `openai`
- `anthropic`
- `openrouter`

`auto` uses the first configured provider.

## Observed Event Flow

The research demo emits:

```text
trace.started
llm.request
llm.response
tool.call.started
tool.call.completed
trace.completed
```

The events are persisted through `OpenMeshCollector.accept()` and therefore
appear in:

- `openmesh events`
- `openmesh traces`
- `openmesh graph`
- `openmesh timeline`
- `openmesh ecosystem`
- `openmesh tui`
- the frontend Graph, Timeline, and Observatory views

## Graph Semantics

The LLM request creates a governed graph relationship:

```text
LLM Research Agent
└─ uses -> gpt-4o-mini
```

The local tool step creates:

```text
LLM Research Agent
└─ uses -> research_brief_builder
```

Relationship provenance includes event ids, trace ids, span ids, first seen,
last seen, and observation counts.

## Safety

OpenMesh never stores API keys in events. Events store provider name, model,
query, response, usage metadata, latency, trace ids, and graph provenance.

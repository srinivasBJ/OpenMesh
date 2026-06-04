# OpenTelemetry Export

OpenMesh can export persisted events into external observability stacks without replacing the OpenMesh collector or graph model.

Exports are derived from the existing OpenMesh event store:

```text
OpenMesh events -> exporter -> external observability stack
```

No external service is required to generate export payloads. Add `--endpoint` only when you want OpenMesh to push the payload.

## Commands

OpenTelemetry Collector:

```bash
openmesh export otel --output openmesh-otlp.json
openmesh export otel --endpoint http://localhost:4318
```

Grafana Tempo uses OTLP HTTP JSON:

```bash
openmesh export tempo --endpoint http://localhost:4318
```

Jaeger:

```bash
openmesh export jaeger --output openmesh-jaeger.json
openmesh export jaeger --endpoint http://localhost:14268
```

Datadog:

```bash
openmesh export datadog --output openmesh-datadog.json
openmesh export datadog --endpoint https://trace.agent.datadoghq.com --api-key "$DD_API_KEY"
```

Prometheus text format:

```bash
openmesh export prometheus --output openmesh.prom
```

## Options

All export targets support:

```bash
--limit 5000
--output path
--endpoint url
--summary
--timeout 10
```

Datadog also supports:

```bash
--api-key "$DD_API_KEY"
```

## Format Mapping

OpenMesh event fields map into external formats as follows:

- `trace_id` -> external trace id
- `span_id` -> external span id
- `parent_span_id` -> parent span reference
- `event_type` -> span operation/name
- `severity` -> span status/error
- `source` and `target` -> attributes/tags/meta
- `payload` -> serialized OpenMesh payload attribute
- `metrics` -> numeric Datadog metrics and serialized OTLP attributes

## Supported Targets

- OpenTelemetry Collector: OTLP HTTP JSON
- Grafana Tempo: OTLP HTTP JSON
- Jaeger: Jaeger trace JSON
- Datadog: Datadog trace JSON
- Prometheus: text exposition metrics

## Validation

Recommended validation:

```bash
openmesh export otel --summary
openmesh export jaeger --summary
openmesh export datadog --summary
openmesh export prometheus --summary
openmesh doctor
python -m unittest discover -s backend/tests
npm run build
```

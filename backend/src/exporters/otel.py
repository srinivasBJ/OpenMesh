from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta
from hashlib import sha256
from typing import Any, Iterable, Literal

import httpx

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import record_to_event


ExportTarget = Literal["otel", "tempo", "jaeger", "datadog", "prometheus"]
OTLP_ENDPOINT_PATH = "/v1/traces"
JAEGER_ENDPOINT_PATH = "/api/traces"
DATADOG_ENDPOINT_PATH = "/api/v0.4/traces"


def build_export_payload(
    records: Iterable[OpenMeshEventRecord],
    target: ExportTarget,
) -> dict[str, Any] | str:
    if target in {"otel", "tempo"}:
        return build_otlp_export(records, target=target)
    if target == "jaeger":
        return build_jaeger_export(records)
    if target == "datadog":
        return build_datadog_export(records)
    if target == "prometheus":
        return build_prometheus_export(records)
    raise ValueError(f"Unsupported export target: {target}")


async def export_records(
    records: Iterable[OpenMeshEventRecord],
    target: ExportTarget,
    *,
    endpoint: str | None = None,
    api_key: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    payload = build_export_payload(records, target)
    summary = export_summary(payload, target)
    result: dict[str, Any] = {
        "target": target,
        "format": _target_format(target),
        "payload": payload,
        "summary": summary,
        "sent": False,
        "endpoint": endpoint,
    }
    if not endpoint:
        return result

    headers = _headers_for_target(target, api_key)
    url = _endpoint_for_target(endpoint, target)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if target == "prometheus":
            response = await client.post(url, content=str(payload), headers=headers)
        else:
            response = await client.post(url, json=payload, headers=headers)
    result.update(
        {
            "sent": True,
            "endpoint": url,
            "status_code": response.status_code,
            "ok": 200 <= response.status_code < 300,
            "response_text": response.text[:500],
        }
    )
    return result


def build_otlp_export(
    records: Iterable[OpenMeshEventRecord], *, target: str = "otel"
) -> dict[str, Any]:
    spans = [_record_to_otlp_span(record) for record in _sorted_records(records)]
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        _otlp_attr("service.name", "openmesh"),
                        _otlp_attr("telemetry.sdk.name", "openmesh"),
                        _otlp_attr("openmesh.export.target", target),
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "openmesh.exporter",
                            "version": "0.1",
                        },
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def build_jaeger_export(records: Iterable[OpenMeshEventRecord]) -> dict[str, Any]:
    traces: dict[str, list[dict[str, Any]]] = {}
    for record in _sorted_records(records):
        event = record_to_event(record)
        trace_id = _trace_id(event.get("trace_id"))
        span_id = _span_id(event.get("span_id") or event.get("event_id"))
        span = {
            "traceID": trace_id,
            "spanID": span_id,
            "operationName": record.event_type,
            "references": _jaeger_references(event, trace_id),
            "startTime": _unix_microseconds(record),
            "duration": 1000,
            "tags": _jaeger_tags(event),
            "processID": "p1",
        }
        traces.setdefault(trace_id, []).append(span)
    return {
        "data": [
            {
                "traceID": trace_id,
                "spans": spans,
                "processes": {
                    "p1": {
                        "serviceName": "openmesh",
                        "tags": [
                            {
                                "key": "openmesh.exporter",
                                "type": "string",
                                "value": "jaeger",
                            }
                        ],
                    }
                },
            }
            for trace_id, spans in traces.items()
        ]
    }


def build_datadog_export(records: Iterable[OpenMeshEventRecord]) -> dict[str, Any]:
    traces: dict[str, list[dict[str, Any]]] = {}
    for record in _sorted_records(records):
        event = record_to_event(record)
        trace_id_text = event.get("trace_id")
        span_id_text = event.get("span_id") or event.get("event_id")
        span = {
            "trace_id": _datadog_id(trace_id_text),
            "span_id": _datadog_id(span_id_text),
            "parent_id": _datadog_id(event.get("parent_span_id")),
            "name": record.event_type,
            "resource": _resource_name(event),
            "service": "openmesh",
            "type": "custom",
            "start": _unix_nanoseconds(record),
            "duration": 1_000_000,
            "error": 1 if record.severity == "error" else 0,
            "meta": _datadog_meta(event),
            "metrics": _numeric_metrics(event.get("metrics", {})),
        }
        traces.setdefault(str(trace_id_text), []).append(span)
    return {"traces": list(traces.values())}


def build_prometheus_export(records: Iterable[OpenMeshEventRecord]) -> str:
    record_list = _sorted_records(records)
    by_event = Counter(record.event_type for record in record_list)
    by_severity = Counter(record.severity for record in record_list)
    traces = {record.trace_id for record in record_list if record.trace_id}
    sessions = {record.session_id for record in record_list if record.session_id}
    lines = [
        "# HELP openmesh_events_total Total OpenMesh events exported.",
        "# TYPE openmesh_events_total counter",
    ]
    for event_type, count in sorted(by_event.items()):
        lines.append(
            f'openmesh_events_total{{event_type="{_label(event_type)}"}} {count}'
        )
    lines.extend(
        [
            "# HELP openmesh_events_by_severity_total Total OpenMesh events by severity.",
            "# TYPE openmesh_events_by_severity_total counter",
        ]
    )
    for severity, count in sorted(by_severity.items()):
        lines.append(
            f'openmesh_events_by_severity_total{{severity="{_label(severity)}"}} {count}'
        )
    lines.extend(
        [
            "# HELP openmesh_traces_total Unique OpenMesh traces exported.",
            "# TYPE openmesh_traces_total gauge",
            f"openmesh_traces_total {len(traces)}",
            "# HELP openmesh_sessions_total Unique OpenMesh sessions exported.",
            "# TYPE openmesh_sessions_total gauge",
            f"openmesh_sessions_total {len(sessions)}",
            "# HELP openmesh_export_events_total Total events included in this export.",
            "# TYPE openmesh_export_events_total gauge",
            f"openmesh_export_events_total {len(record_list)}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_exporter_diagnostics(records: list[Any]) -> dict[str, Any]:
    record_count = len(records)
    return {
        "name": "OpenTelemetry Export",
        "status": "OK",
        "severity": "INFO",
        "detail": {
            "events_available": record_count,
            "targets": ["otel", "jaeger", "tempo", "datadog", "prometheus"],
            "default_protocol": "otlp-http-json",
            "requires_endpoint_for_push": True,
        },
    }


def export_summary(
    payload: dict[str, Any] | str, target: ExportTarget
) -> dict[str, Any]:
    if target == "prometheus":
        metric_lines = [
            line
            for line in str(payload).splitlines()
            if line and not line.startswith("#")
        ]
        return {"metric_lines": len(metric_lines)}
    if target in {"otel", "tempo"}:
        spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
        return {"spans": len(spans), "resource_spans": len(payload["resourceSpans"])}
    if target == "jaeger":
        traces = payload["data"]
        return {
            "traces": len(traces),
            "spans": sum(len(trace["spans"]) for trace in traces),
        }
    traces = payload["traces"]
    return {"traces": len(traces), "spans": sum(len(trace) for trace in traces)}


def _record_to_otlp_span(record: OpenMeshEventRecord) -> dict[str, Any]:
    event = record_to_event(record)
    span = {
        "traceId": _trace_id(event.get("trace_id")),
        "spanId": _span_id(event.get("span_id") or event.get("event_id")),
        "name": record.event_type,
        "kind": 1,
        "startTimeUnixNano": str(_unix_nanoseconds(record)),
        "endTimeUnixNano": str(_unix_nanoseconds(record, offset_ms=1)),
        "attributes": _otlp_attributes(event),
        "status": {
            "code": 2 if record.severity == "error" else 1,
            "message": record.severity,
        },
    }
    if event.get("parent_span_id"):
        span["parentSpanId"] = _span_id(event["parent_span_id"])
    if event.get("links"):
        span["links"] = [
            {
                "traceId": _trace_id(link.get("trace_id") or event.get("trace_id")),
                "spanId": _span_id(link.get("span_id") or link.get("event_id")),
                "attributes": [
                    _otlp_attr("openmesh.link.relationship", link.get("relationship"))
                ],
            }
            for link in event["links"]
            if isinstance(link, dict)
        ]
    return span


def _otlp_attributes(event: dict[str, Any]) -> list[dict[str, Any]]:
    source = event.get("source") or {}
    target = event.get("target") or {}
    attrs = [
        _otlp_attr("openmesh.event_id", event.get("event_id")),
        _otlp_attr("openmesh.event_type", event.get("event_type")),
        _otlp_attr("openmesh.severity", event.get("severity")),
        _otlp_attr("openmesh.session_id", event.get("session_id")),
        _otlp_attr("openmesh.source.node_id", source.get("node_id")),
        _otlp_attr("openmesh.source.node_type", source.get("node_type")),
        _otlp_attr("openmesh.source.name", source.get("name")),
    ]
    if target:
        attrs.extend(
            [
                _otlp_attr("openmesh.target.node_id", target.get("node_id")),
                _otlp_attr("openmesh.target.node_type", target.get("node_type")),
                _otlp_attr("openmesh.target.name", target.get("name")),
            ]
        )
    attrs.extend(
        [
            _otlp_attr("openmesh.payload", event.get("payload", {})),
            _otlp_attr("openmesh.metrics", event.get("metrics", {})),
        ]
    )
    return attrs


def _otlp_attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        encoded = {"boolValue": value}
    elif isinstance(value, int):
        encoded = {"intValue": str(value)}
    elif isinstance(value, float):
        encoded = {"doubleValue": value}
    elif value is None:
        encoded = {"stringValue": ""}
    elif isinstance(value, str):
        encoded = {"stringValue": value}
    else:
        encoded = {"stringValue": json.dumps(value, sort_keys=True, default=str)}
    return {"key": key, "value": encoded}


def _jaeger_references(event: dict[str, Any], trace_id: str) -> list[dict[str, str]]:
    parent_span_id = event.get("parent_span_id")
    if not parent_span_id:
        return []
    return [
        {
            "refType": "CHILD_OF",
            "traceID": trace_id,
            "spanID": _span_id(parent_span_id),
        }
    ]


def _jaeger_tags(event: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": attr["key"], "type": "string", "value": _otlp_value_to_string(attr)}
        for attr in _otlp_attributes(event)
    ]


def _datadog_meta(event: dict[str, Any]) -> dict[str, str]:
    source = event.get("source") or {}
    target = event.get("target") or {}
    meta = {
        "openmesh.event_id": str(event.get("event_id") or ""),
        "openmesh.event_type": str(event.get("event_type") or ""),
        "openmesh.severity": str(event.get("severity") or ""),
        "openmesh.session_id": str(event.get("session_id") or ""),
        "openmesh.source.node_id": str(source.get("node_id") or ""),
        "openmesh.source.node_type": str(source.get("node_type") or ""),
        "openmesh.source.name": str(source.get("name") or ""),
        "openmesh.payload": json.dumps(
            event.get("payload", {}), sort_keys=True, default=str
        ),
    }
    if target:
        meta.update(
            {
                "openmesh.target.node_id": str(target.get("node_id") or ""),
                "openmesh.target.node_type": str(target.get("node_type") or ""),
                "openmesh.target.name": str(target.get("name") or ""),
            }
        )
    return meta


def _numeric_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    values = {}
    for key, value in metrics.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            values[str(key)] = float(value)
    return values


def _resource_name(event: dict[str, Any]) -> str:
    source = event.get("source") or {}
    target = event.get("target") or {}
    if target:
        return f"{source.get('name') or source.get('node_id')} -> {target.get('name') or target.get('node_id')}"
    return str(source.get("name") or source.get("node_id") or event.get("event_type"))


def _target_format(target: ExportTarget) -> str:
    return {
        "otel": "otlp-http-json",
        "tempo": "otlp-http-json",
        "jaeger": "jaeger-json",
        "datadog": "datadog-trace-json",
        "prometheus": "prometheus-text",
    }[target]


def _headers_for_target(target: ExportTarget, api_key: str | None) -> dict[str, str]:
    if target == "prometheus":
        headers = {"Content-Type": "text/plain; version=0.0.4"}
    else:
        headers = {"Content-Type": "application/json"}
    if target == "datadog" and api_key:
        headers["DD-API-KEY"] = api_key
    return headers


def _endpoint_for_target(endpoint: str, target: ExportTarget) -> str:
    cleaned = endpoint.rstrip("/")
    if cleaned.endswith(("/v1/traces", "/api/traces", "/api/v0.4/traces")):
        return cleaned
    if target in {"otel", "tempo"}:
        return cleaned + OTLP_ENDPOINT_PATH
    if target == "jaeger":
        return cleaned + JAEGER_ENDPOINT_PATH
    if target == "datadog":
        return cleaned + DATADOG_ENDPOINT_PATH
    return cleaned


def _sorted_records(
    records: Iterable[OpenMeshEventRecord],
) -> list[OpenMeshEventRecord]:
    return sorted(list(records), key=lambda record: record.timestamp)


def _unix_nanoseconds(record: OpenMeshEventRecord, *, offset_ms: int = 0) -> int:
    timestamp = record.timestamp + timedelta(milliseconds=offset_ms)
    return int(timestamp.timestamp() * 1_000_000_000)


def _unix_microseconds(record: OpenMeshEventRecord) -> int:
    return int(record.timestamp.timestamp() * 1_000_000)


def _trace_id(value: Any) -> str:
    return _hex_id(value, 32)


def _span_id(value: Any) -> str:
    return _hex_id(value, 16)


def _datadog_id(value: Any) -> int:
    return int(_hex_id(value, 16), 16) & 0x7FFFFFFFFFFFFFFF


def _hex_id(value: Any, length: int) -> str:
    seed = str(value or "openmesh")
    return sha256(seed.encode("utf-8")).hexdigest()[:length]


def _otlp_value_to_string(attr: dict[str, Any]) -> str:
    value = attr.get("value", {})
    if "stringValue" in value:
        return str(value["stringValue"])
    if "intValue" in value:
        return str(value["intValue"])
    if "doubleValue" in value:
        return str(value["doubleValue"])
    if "boolValue" in value:
        return str(value["boolValue"]).lower()
    return ""


def _label(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

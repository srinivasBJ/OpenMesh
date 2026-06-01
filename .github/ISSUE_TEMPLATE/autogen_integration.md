---
name: AutoGen Integration
about: Future AutoGen observability integration
title: "AutoGen Integration"
labels: enhancement, integration
assignees: ""
---

## Goal

Add AutoGen instrumentation after the LangGraph reference integration is stable.

## Expected Direction

- Reuse the Python SDK.
- Emit OpenMesh events through the collector.
- Represent agents, messages, tools, and transitions in traces and graph state.

## Non-Goals

- Do not redesign the OpenMesh architecture.
- Do not create a separate event pipeline.

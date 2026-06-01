---
name: OpenHands Integration
about: Future OpenHands observability integration
title: "OpenHands Integration"
labels: enhancement, integration
assignees: ""
---

## Goal

Add OpenHands instrumentation after the LangGraph reference integration is stable.

## Expected Direction

- Reuse the Python SDK.
- Emit OpenMesh events through the collector.
- Represent coding agents, tools, commands, file changes, and runtime status in traces and graph state.

## Non-Goals

- Do not redesign the OpenMesh architecture.
- Do not create a separate event pipeline.

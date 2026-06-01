---
name: CrewAI Integration
about: Future CrewAI observability integration
title: "CrewAI Integration"
labels: enhancement, integration
assignees: ""
---

## Goal

Add CrewAI instrumentation after the LangGraph reference integration is stable.

## Expected Direction

- Reuse the Python SDK.
- Emit OpenMesh events through the collector.
- Represent crews, agents, tasks, tools, and delegation in traces and graph state.

## Non-Goals

- Do not redesign the OpenMesh architecture.
- Do not create a separate event pipeline.

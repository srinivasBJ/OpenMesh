# OpenMesh Architecture Audit

Date: 2026-06-03

## Architecture Score

Overall score: **8.1 / 10**

OpenMesh has successfully shifted from a dashboard-oriented simulation into an event-driven, terminal-first observability core. The strongest architectural decision is that most higher-level views are derived from persisted OpenMesh events instead of separate mutable state. The main remaining risk is that the system is growing many projection services around a flexible JSON event store without enough formal schema/version enforcement, query strategy, or lifecycle boundaries.

Score breakdown:

| Area | Score | Notes |
| --- | ---: | --- |
| Event model | 8.0 | Flexible, protocol-shaped, persisted, but still lightly typed at runtime. |
| Trace/span/session semantics | 7.8 | Good hierarchy support; no materialized span/session linkage beyond events. |
| Graph semantics | 8.3 | Strong relationship governance and provenance; inference remains heuristic. |
| Registry governance | 8.5 | Node/relationship registries and compatibility rules are solid foundations. |
| Discovery and ecosystem mapping | 8.2 | Event-derived, cohesive, terminal-friendly; scaling and duplication rules need hardening. |
| Diagnostics | 8.0 | Broad integrity coverage; severity model and actionable remediation can mature. |
| Operational readiness | 7.2 | SQLite fallback and tests help; migrations, retention, and large-event performance need work. |

## Executive Summary

OpenMesh now has the right architectural spine:

1. Agents, processes, workflows, MCP servers, configs, and capabilities emit or are represented as OpenMesh events.
2. The collector validates and persists events.
3. Trace, graph, discovery, registry, and ecosystem views are reconstructed from persisted events.
4. CLI and TUI consume those derived views directly, keeping the terminal-first product direction intact.

This is the correct shape for the stated goal of becoming an OpenTelemetry-like layer for agent ecosystems. The architecture is not yet production-grade as a protocol standard, but it is coherent enough for the next phase: stronger schema contracts, projection reliability, and operational boundaries.

## Component Audit

### Event Model

Current implementation:

- `OpenMeshEvent` lives in `backend/src/shared/openmesh_events.py`.
- Required envelope fields are validated by `OpenMeshCollector`.
- Events include `event_id`, `event_type`, `timestamp`, `workspace_id`, `session_id`, `trace_id`, `span_id`, `parent_span_id`, `parent_event_id`, `root_event_id`, `source`, `target`, `payload`, `metrics`, `links`, and `severity`.
- Events persist to `openmesh_events` with JSON fields for source, target, payload, metrics, and links.

Strengths:

- Event shape is compact and protocol-like.
- JSON source/target/payload fields allow fast iteration without schema churn.
- `root_event_id`, parent fields, spans, and links give enough structure for hierarchy and cross-trace references.
- Collector validation prevents malformed envelopes and invalid node definitions from entering storage.

Weaknesses:

- Runtime validation is hand-written and partial; there is no canonical schema object such as Pydantic/JSON Schema.
- Event type names are open strings. That is flexible, but it means event semantics can drift.
- `workspace_id` exists in the event builder but is not persisted in `openmesh_events`.
- There is no event schema version compatibility check beyond `spec_version == "0.1"`.
- Payload shape is not governed per event type.

Risks:

- Integrations may emit valid envelopes with semantically incompatible payloads.
- Event type sprawl can make graph inference unpredictable.
- Future protocol version upgrades may be difficult without persisted `workspace_id` and explicit schema metadata.

### Trace Model

Current implementation:

- Trace grouping is based on `trace_id`.
- Trace summaries are produced in `openmesh_queries.py`.
- Trace detail reconstructs events, hierarchy, spans, span tree, graph relationships, and validation from stored records.

Strengths:

- Trace reconstruction is event-derived and does not require separate trace tables.
- `parent_event_id`, `root_event_id`, and `parent_span_id` improve reconstruction beyond timestamp ordering.
- Trace API surfaces hierarchy, spans, relationships, and validation in one place.

Weaknesses:

- Trace status is inferred from event order and event type suffixes.
- Trace summaries only extract agents and tools today, while OpenMesh now models workflows, MCP servers, capabilities, and processes.
- There is no materialized trace index or pagination within large traces.

Risks:

- Large traces may become expensive to reconstruct repeatedly.
- Mixed trace semantics from different integrations may produce inconsistent status.
- Missing `root_event_id` remains recoverable but weakens causal interpretation.

### Span Model

Current implementation:

- Spans are lightweight event fields, not separate records.
- `build_span_summary()` and `build_span_tree()` reconstruct lifecycle and parent-child relationships.
- Span status is inferred from event type suffixes and severity.

Strengths:

- Lightweight, compatible with OpenTelemetry concepts without requiring a full OTel implementation.
- Parent span support is enough for workflow -> node -> tool/process hierarchies.
- Links support cross-trace references.

Weaknesses:

- No explicit span kind, span name, attributes, or status code field.
- Span lifecycle is inferred, not declared.
- A span can exist with only one event, which is useful but makes lifecycle confidence variable.

Risks:

- Different SDKs/integrations may generate span IDs inconsistently.
- Long-running span diagnostics depend on timestamp interpretation and suffix conventions.

### Session Model

Current implementation:

- Sessions are stored in `openmesh_sessions`.
- Process observation creates and completes session records.
- Session detail joins sessions with persisted events by `session_id`.

Strengths:

- Clear local process execution model.
- Tracks command, start/end, status, and exit code.
- Keeps runtime process observation separate from event traces while preserving linkage.

Weaknesses:

- Session records are process-centric; agent SDK tasks and framework workflows may emit `session_id` without corresponding session rows.
- No session metadata beyond command and exit code.
- No workspace/user dimension.

Risks:

- Users may expect all `session_id` values to resolve in `/sessions`, but only CLI process sessions are materialized.

### Node Registry

Current implementation:

- Central node definitions live in `node_types.py`.
- Node validation checks required identifiers, known node type, metadata object shape, deprecated/removed definitions, and unsupported metadata keys.
- Existing types include agent, tool, workflow, process, command, service, framework, mcp_server, capability, model, memory, file, browser, user, runtime, and legacy app nodes.

Strengths:

- Strong governed vocabulary for ecosystem entities.
- Metadata policy is explicit.
- Node definitions carry category and compatibility metadata.

Weaknesses:

- Allowed metadata is a flat key allowlist, not typed metadata.
- Some categories are broad; for example MCP config sources are modeled as `service`.
- Legacy dashboard entities still live beside protocol entities.

Risks:

- Metadata rules can become noisy as integrations add useful fields.
- Broad categories may blur ecosystem semantics unless documented carefully.

### Relationship Registry

Current implementation:

- Central relationship definitions live in `relationship_types.py`.
- Relationship validation checks type, source type, target type, deprecated/removed definitions.
- Graph reducer uses event mappings plus type-based inference.

Strengths:

- Relationship governance is one of the strongest parts of the architecture.
- Edge provenance includes trace/event IDs and observations.
- Supports key ecosystem relationships: `uses`, `runs`, `spawns`, `executes`, `connects_to`, `defines`, `exposes`, `communicates_with`, `delegates_to`, and `transitions_to`.

Weaknesses:

- Inference is partly heuristic: target type alone can imply `uses`, `runs`, or `spawns`.
- Not all workflow-specific events are explicitly mapped; some rely on target/source inference.
- Relationship labels are not versioned per event.

Risks:

- A valid but unexpected source/target pair can create a misleading edge.
- As integrations grow, event-type-specific mappings may need to replace more heuristics.

### Registry Compatibility

Current implementation:

- Node and relationship registry versions are defined in `registry_compatibility.py`.
- Compatibility rules distinguish additive, deprecated, removed, renamed, and unsupported versions.
- Registry status combines definitions, validation metadata, versions, rules, and observed compatibility.

Strengths:

- Good early foundation for protocol evolution.
- Deprecated and removed definitions are part of the model, not an afterthought.
- Doctor surfaces compatibility status.

Weaknesses:

- Current registry major version is `0`, which accurately signals instability.
- Events do not record the registry version they were validated against.
- Compatibility checks apply current registry rules to historical events.

Risks:

- Future registry changes may reinterpret old events incorrectly.
- Without event-time registry version metadata, historical replay may become lossy.

### Discovery

Current implementation:

- `discovery.py` derives observed entities from persisted events.
- Groups are based on node registry categories.
- Framework entries are inferred from node metadata/runtime.

Strengths:

- Discovery is event-derived and generic.
- Automatically benefits from node registry expansion.
- Works for agents, tools, workflows, processes, services, capabilities, and frameworks.

Weaknesses:

- Discovery is limited by the event query limit.
- Framework inference is currently narrow.
- Process grouping uses process name rather than process node ID for category deduplication.

Risks:

- Long-running local environments may produce incomplete discovery if only the most recent events are scanned.
- Duplicate or renamed entities may appear as separate ecosystem objects.

### MCP Registry

Current implementation:

- `mcp_discovery.py` registers and derives MCP server metadata.
- MCP servers are governed `mcp_server` nodes.
- Registration emits `mcp.server.discovered`.

Strengths:

- MCP servers are first-class nodes.
- Metadata-only approach respects the constraint not to connect or execute.
- Graph relationships can connect agents/tools/workflows/services to MCP servers.

Weaknesses:

- Server identity is based on endpoint/name stable IDs, which may not be enough for all transports.
- Registry derivation scans event history rather than a materialized server table.

Risks:

- Multiple configs pointing to the same logical MCP server with different endpoint forms may fragment identity.

### MCP Config Discovery

Current implementation:

- Provider-style config discovery supports Claude Desktop, Claude Code, Codex, and OpenHands paths.
- Parses JSON and TOML.
- Emits `mcp.config.discovered`.
- Represents config source as a governed `service` node defining an `mcp_server`.

Strengths:

- Provider architecture is appropriate and incremental.
- Metadata-only behavior is clear.
- Malformed config and missing metadata diagnostics exist.

Weaknesses:

- Config source uses `service` rather than a dedicated node type.
- Duplicate detection groups by source and server, which may hide path-level nuance.
- Discovery reads local filesystem paths directly from service code.

Risks:

- Config formats can vary significantly; current parser may under-detect valid config forms.
- Config provenance may be too coarse for future trust-chain mapping.

### Capability Registry

Current implementation:

- `mcp_capabilities.py` models capabilities as governed `capability` nodes.
- Emits `mcp.capability.discovered`.
- Graph relationship is `mcp_server -> exposes -> capability`.

Strengths:

- Capability visibility is metadata-only and does not execute tools.
- Fits graph semantics cleanly.
- Doctor validates duplicates, malformed metadata, and missing required fields.

Weaknesses:

- Capability identity is server + capability name only.
- Category is free-form.
- No source config/provenance link between capability declaration and config source yet.

Risks:

- Same capability exposed by multiple MCP servers may be over- or under-deduplicated depending on user expectation.

### Workflow Registry

Current implementation:

- `workflow_registry.py` models workflows as governed `workflow` nodes.
- Tracks workflow, framework, version, source, metadata, last seen.
- Supports graph edges: agent runs workflow, workflow uses tool, workflow connects to MCP server.

Strengths:

- Workflows are correctly first-class ecosystem entities.
- LangGraph alignment is natural without hard-coding LangGraph into core registry logic.
- TUI network now shows workflow edges.

Weaknesses:

- Workflow lifecycle and registry lifecycle are not clearly separated.
- Workflow source is a string, not a structured source reference.
- Duplicate detection is framework + workflow name.

Risks:

- Different versions/sources of the same workflow may collapse in diagnostics while remaining distinct operationally.

### Unified Ecosystem Registry

Current implementation:

- `ecosystem_registry.py` aggregates agents, tools, processes, workflows, MCP servers, MCP configs, and capabilities.
- Uses graph state plus MCP config registry.
- Emits grouped entity inventory and validation.

Strengths:

- Provides the first coherent "whole system" inventory.
- Reuses existing projections and avoids new storage.
- Establishes common entity fields: type, name, status, first_seen, last_seen, relationship_count, and event_count.

Weaknesses:

- It excludes generic `service` nodes except MCP configs and MCP servers.
- MCP configs are synthesized as ecosystem entities, not governed node types.
- Orphan/missing relationship checks are simple and may produce noisy warnings for legitimately standalone entities.

Risks:

- As ecosystem coverage grows, one aggregate function may become a bottleneck.
- Consumers may assume ecosystem entities are stable records, but they are projections.

### Diagnostics

Current implementation:

- `openmesh doctor` checks database, migrations, collector, integrations, trace integrity, workflow integrity, graph integrity, node integrity, relationship integrity, registry compatibility, capability integrity, workflow registry integrity, ecosystem integrity, and MCP configuration integrity.

Strengths:

- Broad coverage across the protocol and registry surface.
- Terminal-friendly severity levels: INFO, WARNING, ERROR.
- Detects broken parent spans, malformed links, graph provenance issues, invalid relationships, node issues, registry compatibility, malformed config, duplicates, and missing metadata.

Weaknesses:

- Severity criteria are inconsistent across domains.
- Diagnostics report counts and details but do not yet link back to precise remediation commands or source events in every case.
- Doctor runs many derived projections repeatedly over the same event set.

Risks:

- On large event stores, doctor may become slow.
- Warning noise can reduce trust if expected standalone entities are reported as ecosystem issues.

## Cross-Cutting Strengths

- Terminal-first architecture is real, not cosmetic. CLI and TUI consume core services directly.
- Most state is event-derived, which keeps the system auditable.
- Registries are governed centrally rather than scattered through UI code.
- Graph edges include provenance, observation counts, lifecycle state, and validation state.
- SQLite fallback makes local development approachable.
- Tests cover major protocol, registry, graph, trace, CLI, and TUI behavior.
- The dashboard remains a visualization layer rather than the source of truth.

## Cross-Cutting Weaknesses

- Projection services scan recent events with fixed limits; this can produce partial views.
- The event schema is not formalized as machine-readable JSON Schema or Pydantic models.
- Event payloads are not typed per event type.
- Migration files and SQLAlchemy initialization are not fully aligned; `init_db()` patches trace columns imperatively.
- There are many root-level and backend duplicate untracked files with ` 2` suffixes in the working tree, which increases repository hygiene risk.
- Registries are growing horizontally; common projection helpers could reduce duplication later.
- Historical replay is based on current registry definitions, not event-time definitions.

## Key Risks

1. **Projection scalability**

   Discovery, graph, registries, ecosystem, and diagnostics rebuild from event scans. This is fine for MVP, but will degrade as event volume grows.

2. **Schema drift**

   Flexible event payloads and string event types are productive now but risky for external SDKs and integrations.

3. **Identity fragmentation**

   Stable IDs are generated differently across servers, workflows, configs, capabilities, and processes. Equivalent real-world entities may split into multiple nodes.

4. **Diagnostic noise**

   Orphans, missing relationships, and unsupported metadata warnings may become noisy as more integrations emit partial metadata.

5. **Historical compatibility**

   Registry versions are not persisted with events, making old event interpretation dependent on current registry definitions.

6. **Session consistency**

   Sessions exist as materialized records for process runs, but many protocol events carry session IDs that do not correspond to `openmesh_sessions`.

## Technical Debt

- Formal event schema is still implicit in Python types and collector validation.
- No event retention, compaction, or archival strategy.
- No materialized projections for graph, discovery, trace summaries, ecosystem, or registries.
- No migration runner or consistent migration history enforcement.
- No structured source reference model for configs, workflow source, or capability declaration source.
- CLI/TUI display functions are growing alongside service logic; presentation concerns may need light cleanup later.
- Graph relationship inference still mixes explicit event mappings with heuristic type inference.
- Diagnostics rebuild overlapping state repeatedly.
- Test fixtures are concentrated in one large core test file.

## Recommended Next Milestones

These are recommendations only; this audit does not implement them.

1. **Protocol Schema Hardening**

   Define a canonical machine-readable OpenMesh event schema and event-type payload contracts. Keep compatibility with the current event shape.

2. **Projection Query Strategy**

   Introduce clear pagination and full-history options for graph, discovery, registries, and ecosystem views before adding more integrations.

3. **Identity Normalization**

   Define identity rules for agents, workflows, MCP servers, configs, capabilities, tools, and processes so equivalent entities converge reliably.

4. **Registry Version Persistence**

   Persist node and relationship registry versions, or at least protocol registry metadata, with events at ingestion time.

5. **Diagnostics Refinement**

   Normalize severity rules and add event IDs/source metadata consistently to every diagnostic detail.

6. **Projection Performance Baseline**

   Add benchmark-style tests or fixtures for thousands of events to measure graph, trace, ecosystem, and doctor performance.

7. **Migration Hygiene**

   Consolidate migration strategy around SQLAlchemy initialization or a migration runner, and remove duplicate migration artifacts from the working tree.

8. **Session Semantics Clarification**

   Decide whether all protocol sessions should be materialized or whether `openmesh_sessions` is intentionally limited to process execution.

9. **Registry Documentation Pass**

   Document the governed vocabularies for node types, relationship types, ecosystem entity types, and metadata expectations in one protocol-facing reference.

## Final Assessment

OpenMesh is architecturally on the right path. The event-first model, governed graph vocabulary, protocol-derived registries, and terminal-native interfaces form a coherent foundation for agent ecosystem observability. The current system should avoid adding more feature surface until schema contracts, projection scaling, identity rules, and migration hygiene are tightened.

The next phase should be stabilization, not expansion.

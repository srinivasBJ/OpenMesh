# OpenMesh Protocol v1 Compatibility Rules

OpenMesh v1 is designed for additive evolution.

## Compatible Changes

The following changes are compatible within v1:

- adding optional fields
- adding event types
- adding payload keys
- adding metadata keys
- adding metrics keys
- adding link relationship values
- adding query examples
- adding replay frame actions
- adding timeline entry kinds
- adding registry definitions when consumers can ignore unknown definitions

Consumers MUST preserve unknown fields when possible.

## Incompatible Changes

The following changes require a new major protocol version:

- changing required field names
- changing required field types
- removing required fields
- removing node types
- removing relationship types
- reversing relationship direction semantics
- changing trace or span identity semantics
- removing provenance requirements from relationships

## Deprecated Definitions

Deprecated node or relationship definitions remain valid in v1 until a future major version removes them.

Producers SHOULD stop emitting deprecated definitions after a replacement exists.

Consumers SHOULD report deprecated definitions as warnings, not errors.

## Removed Definitions

Removed definitions are invalid for the version in which they are removed.

Consumers SHOULD report removed definitions as errors.

## Unknown Fields

Unknown fields are allowed in v1 payloads.

Consumers SHOULD:

- keep unknown fields in exported snapshots
- keep unknown fields in replay and query results when they are part of source evidence
- ignore unknown fields for validation unless a local policy says otherwise

## Unknown Node Types

Unknown node types are invalid for governed graph validation in v1.

Forward-compatible consumers MAY retain unknown node records as raw event payload data, but SHOULD NOT promote them to governed graph nodes without a registry update.

## Unknown Relationship Types

Unknown relationship types are invalid for governed graph validation in v1.

Consumers MAY retain raw relationship evidence, but SHOULD NOT treat unknown relationships as governed graph edges.

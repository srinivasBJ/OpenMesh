# OpenMesh Protocol v1 Versioning Strategy

OpenMesh Protocol versions use `MAJOR.MINOR`.

Protocol v1 uses:

```text
spec_version: "1.0"
schema_version: "1.0"
```

## Version Fields

- Events use `spec_version`.
- Snapshots use `schema_version`.
- JSON Schemas are named with `.v1.schema.json`.
- Registry definitions expose independent node and relationship registry versions.

## Major Versions

A major version changes when OpenMesh makes an incompatible protocol change.

Examples:

- removing a required field
- changing a field type
- renaming a field without compatibility aliases
- removing a node type
- removing a relationship type
- changing relationship direction semantics

## Minor Versions

A minor version changes when OpenMesh makes additive compatible changes.

Examples:

- adding an optional field
- adding a new event type
- adding a new node type
- adding a new relationship type
- adding a new query form
- adding a new replay frame category

## Schema Versioning

Schema filenames remain major-versioned:

```text
openmesh-event.v1.schema.json
openmesh-trace.v1.schema.json
```

Within the file, `$id` identifies the protocol major version and schema purpose.

Patch-level documentation changes do not require schema filename changes.

## Consumer Guidance

Consumers SHOULD:

- accept fields they do not understand
- validate required fields
- retain unknown payload and metadata fields
- reject unknown major versions unless explicitly configured

Consumers MUST NOT:

- assume event order alone defines causality
- drop provenance when transforming relationships
- rewrite trace ids, span ids, event ids, or session ids

# OpenMesh Plugins

OpenMesh plugins are discoverable integration packages that expose metadata and,
optionally, a loadable entry point.

The current plugin registry discovers plugins from:

- module-level `OPENMESH_PLUGIN` dictionaries in `src.sdk.integrations`
- installed Python entry points in the `openmesh.plugins` group

## Commands

```bash
openmesh plugins
openmesh plugins list
openmesh plugins inspect langgraph
openmesh plugins validate langgraph
```

`openmesh integrations` remains available as a compatibility view over plugins
whose `kind` is `integration`.

## Metadata

```python
OPENMESH_PLUGIN = {
    "plugin_id": "langgraph",
    "name": "LangGraph",
    "version": "0.1.0",
    "plugin_api_version": "1.0",
    "kind": "integration",
    "status": "reference",
    "package": "langgraph",
    "entrypoint": "OpenMeshLangGraph",
    "description": "Observe LangGraph workflow and node lifecycle events.",
    "capabilities": ["workflow.lifecycle", "node.lifecycle"],
    "metadata": {"framework": "LangGraph"},
}
```

Required fields:

- `plugin_id`
- `name`
- `version`
- `plugin_api_version`
- `kind`
- `module`

For module-discovered plugins, `module` is filled automatically by discovery.

## Validation

The registry validates:

- required metadata fields
- plugin id format
- plugin API major-version compatibility
- importable plugin module
- optional dependency availability
- loadable entrypoint when one is declared

Validation is informational unless metadata is invalid. Missing optional
dependencies produce warnings so planned or not-installed integrations can still
appear in inventory views.

`openmesh plugins validate <plugin>` exits with status `1` only when plugin
metadata is invalid. Warnings such as missing optional dependencies keep the
plugin discoverable.

## Versioning

OpenMesh exposes two plugin version fields:

- `registry_version`: the OpenMesh plugin registry metadata format.
- `plugin_api_version`: the plugin API contract declared by a plugin.

OpenMesh currently accepts plugins whose `plugin_api_version` has the same major
version as the supported plugin API. Minor and patch changes are treated as
compatible additive changes. Future breaking changes should increment the major
version and report unsupported plugins through validation.

## Loading

Plugins load through `src.services.plugins.load_plugin(plugin_id)`.

Loading imports the plugin module and resolves the declared entrypoint. Runtime
events still flow through the existing SDK, collector, persistence, trace,
graph, discovery, and ecosystem registry pipeline.

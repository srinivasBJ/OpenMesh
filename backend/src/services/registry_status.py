from __future__ import annotations

from typing import Any, Iterable, Optional

from ..db.models import OpenMeshEventRecord
from .graph_state import reduce_graph_state
from .node_types import node_type_registry, node_type_validation_metadata
from .registry_compatibility import compatibility_status, registry_versions, validate_registry_versions
from .relationship_types import relationship_registry, relationship_registry_metadata


def build_registry_status(
    records: Optional[Iterable[OpenMeshEventRecord]] = None,
    *,
    node_registry_version: str | None = None,
    relationship_registry_version: str | None = None,
) -> dict[str, Any]:
    validation = {}
    if records is not None:
        graph = reduce_graph_state(records)
        validation = graph.get("validation", {})

    version_validation = validate_registry_versions(
        node_registry_version=node_registry_version,
        relationship_registry_version=relationship_registry_version,
    )
    observed_compatibility = compatibility_status(
        version_validation=version_validation,
        deprecated_nodes=validation.get("deprecated_node_types", []),
        deprecated_relationships=validation.get("deprecated_relationship_types", []),
        removed_nodes=validation.get("removed_node_types", []),
        removed_relationships=validation.get("removed_relationship_types", []),
    )

    return {
        "versions": registry_versions(),
        "checked_versions": version_validation["versions"],
        "node_definitions": node_type_registry(),
        "relationship_definitions": relationship_registry(),
        "validation": {
            "node_registry": node_type_validation_metadata(),
            "relationship_registry": relationship_registry_metadata(),
        },
        "compatibility": observed_compatibility,
        "rules": version_validation["rules"],
    }

# OpenMesh Decisions

## LangGraph Is The First Reference Integration

Decision: LangGraph is the first framework integration for OpenMesh.

Reason: LangGraph's node and edge execution model aligns naturally with OpenMesh graph and trace architecture. Nodes map cleanly to observable OpenMesh nodes, and transitions map cleanly to graph relationships.

Consequence: Future framework integrations should reuse the SDK -> collector -> persistence -> traces -> graph pipeline proven by LangGraph.

## Analysis Is A Future Layer

Decision: Active MCP discovery and security analysis stay on the roadmap, but are not part of the current implementation milestone.

Reason: OpenMesh must first provide dependable discovery, registry, relationship mapping, and observability primitives. Analysis should build on those primitives instead of creating a separate pipeline.

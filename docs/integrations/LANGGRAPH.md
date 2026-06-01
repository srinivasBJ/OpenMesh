# LangGraph Integration

OpenMesh can observe LangGraph workflows by wrapping node callables with the Python SDK integration.

```python
from src.sdk import OpenMeshClient
from src.sdk.integrations.langgraph import OpenMeshLangGraph

mesh = OpenMeshLangGraph(client=OpenMeshClient(), graph_name="Research Flow")

workflow.add_node("Research", mesh.node("Research", research_node))
workflow.add_node("Summarize", mesh.node("Summarize", summarize_node))
mesh.add_edge(workflow, "Research", "Summarize")
```

The wrapper emits:

- `node.started`
- `node.completed`
- `node.failed`
- `node.transition`

Each LangGraph node is represented as an OpenMesh `service` node with `runtime: langgraph`. Use `mesh.add_edge(...)` when building a workflow so declared LangGraph edges become OpenMesh `node.transition` relationships. For custom runners, call `mesh.transition("Node A", "Node B")` explicitly.

Events use the normal OpenMesh collector path, so they appear in:

```bash
python -m src.cli.openmesh events
python -m src.cli.openmesh traces
python -m src.cli.openmesh graph
python -m src.cli.openmesh tui
```

Run the example:

```bash
pip install langgraph
python examples/langgraph_basic.py
```

Check integration registry state:

```python
from src.sdk.integrations import list_integrations

print(list_integrations())
```

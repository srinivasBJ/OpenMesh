# CrewAI Integration

The CrewAI adapter observes crew workflows, agents, tasks, task transitions, and
tool calls. It emits normal OpenMesh events and does not create a separate graph
model.

```python
from src.sdk import OpenMeshClient
from src.sdk.integrations.crewai import OpenMeshCrewAI

mesh = OpenMeshCrewAI(client=OpenMeshClient(), crew_name="Research Crew")
researcher = mesh.agent(name="Research Agent", role="Researcher")

with mesh.workflow():
    with researcher.task("Research OpenMesh") as task:
        with task.tool("web_search"):
            pass
```

Run:

```bash
python examples/crewai_basic.py
openmesh discover
openmesh graph --details
```

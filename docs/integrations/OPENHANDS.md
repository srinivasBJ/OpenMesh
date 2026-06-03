# OpenHands Integration

The OpenHands adapter observes coding-session metadata: agent identity, workflow
lifecycle, actions, tools, commands, and file modifications.

```python
from src.sdk import OpenMeshClient
from src.sdk.integrations.openhands import OpenMeshOpenHands

mesh = OpenMeshOpenHands(client=OpenMeshClient(), workflow_name="Coding Session")
agent = mesh.coding_agent()

with mesh.workflow():
    with mesh.observe_action("Inspect failing tests", agent=agent) as task:
        with task.tool("terminal"):
            mesh.observe_command("pytest", agent=agent)
    mesh.observe_file("backend/src/app.py", agent=agent)
```

Run:

```bash
python examples/openhands_basic.py
openmesh inspect openhands-agent
openmesh graph --details
```

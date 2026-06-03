# AutoGen Integration

The AutoGen adapter observes agents, group-chat workflows, messages, tasks, and
tool calls. It is dependency-light: pass AutoGen objects when available, or use
explicit handles around a custom runner.

```python
from src.sdk import OpenMeshClient
from src.sdk.integrations.autogen import OpenMeshAutoGen

mesh = OpenMeshAutoGen(client=OpenMeshClient(), workflow_name="Research Chat")
user = mesh.user_proxy(name="User Proxy")
assistant = mesh.assistant(name="Assistant")

with mesh.workflow():
    mesh.observe_message(user, assistant, content="Research OpenMesh.")
    with assistant.task("Research graph provenance") as task:
        with task.tool("web_search"):
            pass
```

Run:

```bash
python examples/autogen_basic.py
openmesh discover
openmesh graph --details
```

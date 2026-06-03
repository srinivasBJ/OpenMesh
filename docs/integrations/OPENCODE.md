# OpenCode Integration

The OpenCode adapter observes terminal coding-agent metadata: prompts, tools,
commands, file modifications, workflow lifecycle, and agent identity.

```python
from src.sdk import OpenMeshClient
from src.sdk.integrations.opencode import OpenMeshOpenCode

mesh = OpenMeshOpenCode(client=OpenMeshClient())
agent = mesh.coding_agent()

mesh.observe_event(
    {
        "prompt": "Add benchmark tests",
        "tool": "patch",
        "command": "ruff check .",
        "path": "backend/tests/test_openmesh_core.py",
        "exit_code": 0,
    },
    agent=agent,
)
```

Run:

```bash
python examples/opencode_basic.py
openmesh discover
openmesh graph --details
```

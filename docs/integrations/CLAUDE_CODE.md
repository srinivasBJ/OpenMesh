# Claude Code Integration

The Claude Code adapter observes CLI-visible metadata and hook-style payloads.
It records prompts/messages, tool names, command metadata, and modified files.

It does not execute tools, inspect credentials, or depend on private Claude Code
internals.

```python
from src.sdk import OpenMeshClient
from src.sdk.integrations.claude_code import OpenMeshClaudeCode

mesh = OpenMeshClaudeCode(client=OpenMeshClient())
agent = mesh.coding_agent()

mesh.observe_hook_event(
    {
        "prompt": "Patch graph output",
        "tool_name": "Edit",
        "command": "ruff check .",
        "file_path": "backend/src/cli/openmesh.py",
        "exit_code": 0,
    },
    agent=agent,
)
```

Run:

```bash
python examples/claude_code_basic.py
openmesh discover
openmesh query agents using Edit
```

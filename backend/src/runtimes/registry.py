from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
from typing import Iterable


@dataclass(frozen=True)
class RuntimeDefinition:
    runtime_id: str
    name: str
    command_names: tuple[str, ...]
    aliases: tuple[str, ...]
    detection_paths: tuple[str, ...] = ()
    agent_name: str | None = None


@dataclass(frozen=True)
class RuntimeStatus:
    runtime_id: str
    name: str
    available: bool
    status: str
    message: str
    executable: str | None = None
    path: str | None = None
    detection_method: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


RUNTIME_DEFINITIONS: tuple[RuntimeDefinition, ...] = (
    RuntimeDefinition(
        runtime_id="claude_code",
        name="Claude Code",
        command_names=("claude",),
        aliases=("claude", "claude-code", "claude_code"),
        agent_name="Claude Code Agent",
    ),
    RuntimeDefinition(
        runtime_id="codex_cli",
        name="Codex CLI",
        command_names=("codex",),
        aliases=("codex", "codex-cli", "codex_cli"),
        agent_name="Codex CLI Agent",
    ),
    RuntimeDefinition(
        runtime_id="opencode",
        name="OpenCode",
        command_names=("opencode",),
        aliases=("opencode", "open-code", "open_code"),
        agent_name="OpenCode Agent",
    ),
    RuntimeDefinition(
        runtime_id="aider",
        name="Aider",
        command_names=("aider",),
        aliases=("aider",),
        agent_name="Aider Agent",
    ),
    RuntimeDefinition(
        runtime_id="cursor",
        name="Cursor",
        command_names=("cursor",),
        aliases=("cursor", "cursor-agent", "cursor_agent"),
        detection_paths=(
            "/Applications/Cursor.app",
            "~/Applications/Cursor.app",
        ),
        agent_name="Cursor Agent Workflow",
    ),
)

_DEFINITIONS_BY_ID = {
    definition.runtime_id: definition for definition in RUNTIME_DEFINITIONS
}
_ALIASES = {
    alias: definition.runtime_id
    for definition in RUNTIME_DEFINITIONS
    for alias in (definition.runtime_id, definition.name.lower(), *definition.aliases)
}


def canonical_runtime_id(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    return _ALIASES.get(
        normalized.replace("_", "-"), _ALIASES.get(normalized, normalized)
    )


def get_runtime_definition(runtime_id: str) -> RuntimeDefinition | None:
    return _DEFINITIONS_BY_ID.get(canonical_runtime_id(runtime_id))


def discover_runtimes(
    definitions: Iterable[RuntimeDefinition] = RUNTIME_DEFINITIONS,
) -> list[RuntimeStatus]:
    return [detect_runtime(definition) for definition in definitions]


def detect_runtime(definition: RuntimeDefinition) -> RuntimeStatus:
    for command_name in definition.command_names:
        executable = shutil.which(command_name)
        if executable:
            return RuntimeStatus(
                runtime_id=definition.runtime_id,
                name=definition.name,
                available=True,
                status="installed",
                message="installed",
                executable=executable,
                detection_method="path",
            )

    for raw_path in definition.detection_paths:
        path = Path(raw_path).expanduser()
        if path.exists():
            return RuntimeStatus(
                runtime_id=definition.runtime_id,
                name=definition.name,
                available=True,
                status="detected",
                message="detected",
                path=str(path),
                detection_method="filesystem",
            )

    return RuntimeStatus(
        runtime_id=definition.runtime_id,
        name=definition.name,
        available=False,
        status="missing",
        message="missing",
    )

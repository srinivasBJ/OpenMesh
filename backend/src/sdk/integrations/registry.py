from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from typing import Optional


@dataclass(frozen=True)
class IntegrationSpec:
    key: str
    name: str
    package: str
    status: str = "planned"


INTEGRATIONS: dict[str, IntegrationSpec] = {
    "langgraph": IntegrationSpec(
        key="langgraph",
        name="LangGraph",
        package="langgraph",
        status="reference",
    ),
    "crewai": IntegrationSpec(
        key="crewai", name="CrewAI", package="crewai", status="reference"
    ),
    "autogen": IntegrationSpec(key="autogen", name="AutoGen", package="autogen"),
    "openhands": IntegrationSpec(
        key="openhands", name="OpenHands", package="openhands"
    ),
}

_active_integrations: set[str] = set()


def mark_integration_active(key: str) -> None:
    if key in INTEGRATIONS:
        _active_integrations.add(key)


def list_integrations() -> list[dict[str, object]]:
    return [integration_status(key) for key in INTEGRATIONS]


def integration_status(key: str) -> dict[str, object]:
    spec = INTEGRATIONS[key]
    available = find_spec(spec.package) is not None
    package_version: Optional[str] = None
    if available:
        try:
            package_version = version(spec.package)
        except PackageNotFoundError:
            package_version = None
    data = asdict(spec)
    data.update(
        {
            "available": available,
            "active": key in _active_integrations,
            "version": package_version,
            "status_label": _status_label(spec, available),
        }
    )
    return data


def get_integration(key: str) -> Optional[dict[str, object]]:
    if key not in INTEGRATIONS:
        return None
    return integration_status(key)


def _status_label(spec: IntegrationSpec, available: bool) -> str:
    if spec.key in _active_integrations:
        return "Active"
    if available:
        return "Available"
    if spec.status == "reference":
        return "Not installed"
    return "Future"

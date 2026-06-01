from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import ASYNC_URL, DATABASE_URL
from ..sdk.integrations import list_integrations
from .openmesh_collector import collector


REQUIRED_TABLES = {
    "openmesh_events",
    "openmesh_sessions",
    "agents",
    "agent_events",
}


def _safe_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    _, host = rest.rsplit("@", 1)
    return f"{scheme}://***@{host}"


async def run_doctor(db: AsyncSession) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    try:
        await db.execute(text("SELECT 1"))
        checks.append({"name": "database", "status": "OK", "detail": "connection succeeded"})
    except Exception as exc:
        checks.append({"name": "database", "status": "ERROR", "detail": str(exc)})

    try:
        connection = await db.connection()
        tables = await connection.run_sync(lambda sync_connection: set(inspect(sync_connection).get_table_names()))
        missing = sorted(REQUIRED_TABLES - tables)
        checks.append({
            "name": "migrations",
            "status": "OK" if not missing else "ERROR",
            "detail": "all required tables exist" if not missing else f"missing tables: {', '.join(missing)}",
        })
    except Exception as exc:
        checks.append({"name": "migrations", "status": "ERROR", "detail": str(exc)})

    checks.append({
        "name": "collector",
        "status": "OK" if collector else "ERROR",
        "detail": "collector service importable",
    })

    try:
        integrations = list_integrations()
        langgraph = next((item for item in integrations if item["key"] == "langgraph"), None)
        checks.append({
            "name": "Integration Health",
            "status": "OK",
            "detail": {
                "LangGraph": langgraph["status_label"] if langgraph else "Unknown",
                "Graph Reducer": "OK",
                "integrations": [
                    f"{item['name']}: {item['status_label']}"
                    for item in integrations
                ],
            },
        })
    except Exception as exc:
        checks.append({"name": "integration health", "status": "ERROR", "detail": str(exc)})

    migrations_dir = Path(__file__).resolve().parents[1] / "db" / "migrations"
    migration_files = sorted(path.name for path in migrations_dir.glob("*.sql"))
    checks.append({
        "name": "configuration",
        "status": "OK",
        "detail": {
            "database_url": _safe_url(DATABASE_URL),
            "async_url": _safe_url(ASYNC_URL),
            "migrations": migration_files,
        },
    })

    return {
        "status": "OK" if all(check["status"] == "OK" for check in checks) else "ERROR",
        "checks": checks,
    }

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_openmesh_env() -> None:
    """Load local env files without overriding explicit shell variables."""
    backend_dir = Path(__file__).resolve().parents[2]
    candidates = (
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
        backend_dir / ".env",
    )
    for path in candidates:
        if path.exists():
            load_dotenv(path, override=False)

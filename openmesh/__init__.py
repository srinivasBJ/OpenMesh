from __future__ import annotations

from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if BACKEND_ROOT.exists() and str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.sdk import AgentHandle, OpenMeshClient  # noqa: E402

__all__ = ["AgentHandle", "OpenMeshClient"]

"""
Filesystem browsing for the repository-path picker.

Browsers cannot expose absolute paths from a native folder picker, so the
workspace creation flow browses server-side instead.

Security: listing is restricted to the user's home directory subtree,
returns directories only, and hides dotfiles. Read-only.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

MAX_ENTRIES = 300


@router.get("/filesystem/browse")
async def browse_filesystem(path: str | None = Query(default=None)):
    home = Path.home().resolve()
    target = Path(path).expanduser() if path else home
    try:
        target = target.resolve()
    except OSError:
        raise HTTPException(400, "Invalid path")
    if target != home and home not in target.parents:
        raise HTTPException(400, "Browsing is restricted to your home directory")
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, "Directory not found")
    try:
        children = [
            child
            for child in target.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ]
    except PermissionError:
        raise HTTPException(403, "Permission denied")
    children.sort(key=lambda child: child.name.lower())
    return {
        "path": str(target),
        "parent": str(target.parent) if target != home else None,
        "home": str(home),
        "directories": [
            {"name": child.name, "path": str(child)}
            for child in children[:MAX_ENTRIES]
        ],
        "truncated": len(children) > MAX_ENTRIES,
    }

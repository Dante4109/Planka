"""
Shortcuts — aliases for frequently used commands, like a PowerShell alias.

Defined in shortcuts.json (PT_SHORTCUTS env var, else ./shortcuts.json, else the repo root):

    {"done": "card move-all -p 'Trello Import Dev' -b 'Daily Workflow' -l {} -l Done"}

`pt done "this month"` then runs `pt card move-all ... -l "this month" -l Done`.
Each `{}` takes the next argument; any extra arguments are appended.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path


def _load() -> dict[str, str]:
    candidates = [os.environ.get("PT_SHORTCUTS"), "shortcuts.json", Path(__file__).parents[3] / "shortcuts.json"]
    for c in candidates:
        if c and Path(c).is_file():
            return json.loads(Path(c).read_text(encoding="utf-8"))
    return {}


def expand(argv: list[str]) -> list[str]:
    """If argv[0] names a shortcut, return its expanded command line; else argv unchanged."""
    shortcuts = _load()
    if not argv or argv[0] not in shortcuts:
        return argv
    args = iter(argv[1:])
    out = [next(args, "") if t == "{}" else t for t in shlex.split(shortcuts[argv[0]])]
    return out + list(args)

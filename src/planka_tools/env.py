"""
Shared env-file resolution so the CLI can target different Planka instances.

Selecting an env file (first match wins):
  1. ``pt --env NAME ...``  (sets PLANKA_ENV for the process)
  2. ``PLANKA_ENV=NAME`` in the shell

NAME resolves to ``<repo>/.env.NAME``; a value that is an existing file path
(or contains a path separator) is used as-is. With no selection the default
``<repo>/.env`` is used.

Precedence for a key:
  - default (.env):   real environment variable, then the file
  - named env file:   the file, then the real environment variable
    (so a stray PLANKA_API_KEY in your shell can't hit the wrong instance)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

ENV_SELECTOR = "PLANKA_ENV"
_ROOT = Path(__file__).resolve().parents[2]


def env_file() -> Path:
    name = os.environ.get(ENV_SELECTOR, "").strip()
    if not name:
        return _ROOT / ".env"
    candidate = Path(name)
    if candidate.is_file() or candidate.parent != Path("."):
        return candidate
    return _ROOT / f".env.{name}"


@lru_cache(maxsize=None)
def _read(path: Path) -> dict:
    return dict(dotenv_values(path)) if path.is_file() else {}


def load_env(key: str, default: Optional[str] = None) -> Optional[str]:
    selected = bool(os.environ.get(ENV_SELECTOR, "").strip())
    file_val = _read(env_file()).get(key)
    env_val = os.environ.get(key)
    first, second = (file_val, env_val) if selected else (env_val, file_val)
    return first or second or default


def select(name: str) -> None:
    """Select a named env file for this process; fail early if it's missing."""
    os.environ[ENV_SELECTOR] = name
    path = env_file()
    if not path.is_file():
        raise FileNotFoundError(f"Env file not found: {path}")

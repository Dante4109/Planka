"""
loader.py — Auto-discovery for job modules under jobs/Scheduled/ and jobs/Webhook/.

Each `.py` file (except __init__.py) in the given directory is imported by
file path (not package-relative import, since job files aren't declared in
any __init__.py). A module must expose the attributes required for its job
type (see base.py) or it is logged and skipped. Any error raised while
importing a module — syntax error, missing attribute, or an exception at
module scope — is caught, logged, and the module is skipped so one bad job
file never prevents the others from loading.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType

log = logging.getLogger(__name__)


def _load_module_from_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_jobs(jobs_dir: Path, required_attrs: tuple[str, ...]) -> list[ModuleType]:
    modules: list[ModuleType] = []
    if not jobs_dir.exists():
        return modules
    for path in sorted(jobs_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            module = _load_module_from_path(path)
            for attr in required_attrs:
                if not hasattr(module, attr):
                    raise AttributeError(f"missing required attribute '{attr}'")
            modules.append(module)
        except Exception as exc:
            log.error("Failed to load job module %s: %s", path, exc)
    return modules


def load_scheduled_jobs(jobs_dir: Path) -> list[ModuleType]:
    """Load and validate all Scheduled job modules in jobs_dir."""
    return _load_jobs(jobs_dir, required_attrs=("TRIGGER", "run"))


def load_webhook_jobs(jobs_dir: Path) -> list[ModuleType]:
    """Load and validate all Webhook job modules in jobs_dir."""
    return _load_jobs(jobs_dir, required_attrs=("EVENTS", "run"))

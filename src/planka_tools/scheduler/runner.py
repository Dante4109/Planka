"""
runner.py — APScheduler-based automation runner.

Reads job configuration from PLANKA_AUTOMATION_BOARDS in .env or the
environment (comma-separated list of board IDs), then polls each board
on a configurable interval to keep list point totals in sync.

Environment variables (all optional):
  PLANKA_AUTOMATION_BOARDS   Comma-separated board IDs to watch.
                             e.g. "1784419684444013580,1784419684444013581"
  PLANKA_POINTS_FIELD        Custom field name to sum (default: "Points")
  PLANKA_POLL_INTERVAL       Polling interval in seconds (default: 60)
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from planka_tools.api.client import PlankaClient, PlankaError
from planka_tools.automations.list_points import sync_list_point_totals
from planka_tools.jobs import loader

log = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


def _load_env(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1]
    return default


def _make_job(board_id: str, points_field: str):
    """Return a scheduler job function for one board."""

    def job():
        log.info("Syncing board %s ...", board_id)
        try:
            with PlankaClient() as client:
                changes = sync_list_point_totals(client, board_id, points_field)
            for c in changes:
                log.info("  '%s'  →  '%s'  (total: %s)", c.old_name, c.new_name, c.total)
            if not changes:
                log.debug("  Board %s: no changes.", board_id)
        except PlankaError as e:
            log.error("API error on board %s: %s", board_id, e)
        except Exception as e:
            log.error("Unexpected error on board %s: %s", board_id, e)

    job.__name__ = f"sync_points_{board_id}"
    return job


def _jobs_dir() -> Path:
    """Base directory for discovered job scripts (Scheduled/, Webhook/ subdirs)."""
    override = _load_env("JOBS_DIR")
    return Path(override) if override else Path(__file__).resolve().parents[1] / "jobs"


def _make_scheduled_job_runner(module):
    """Return a scheduler job function that runs a discovered job module's run(client)."""

    def job():
        log.info("Running discovered job '%s' ...", module.__name__)
        try:
            with PlankaClient() as client:
                module.run(client)
        except PlankaError as e:
            log.error("API error in job %s: %s", module.__name__, e)
        except Exception as e:
            log.error("Unexpected error in job %s: %s", module.__name__, e)

    job.__name__ = f"jobs_{module.__name__}"
    return job


def load_and_register_jobs(scheduler: BlockingScheduler, jobs_dir: Path) -> list[str]:
    """Discover Scheduled job modules under jobs_dir and register them with the scheduler."""
    registered = []
    for module in loader.load_scheduled_jobs(jobs_dir / "Scheduled"):
        trig = dict(module.TRIGGER)
        trig_type = trig.pop("type", "cron")
        trigger = CronTrigger(**trig) if trig_type == "cron" else IntervalTrigger(**trig)
        job_id = f"jobs_{module.__name__}"
        scheduler.add_job(
            _make_scheduled_job_runner(module),
            trigger=trigger,
            id=job_id,
            name=module.__name__,
            max_instances=1,
            coalesce=True,
        )
        registered.append(job_id)
    return registered


def build_scheduler() -> tuple[BlockingScheduler, list[str]]:
    """Build and return a configured scheduler and the list of board IDs registered."""
    raw_boards = _load_env("PLANKA_AUTOMATION_BOARDS")
    board_ids = [b.strip() for b in raw_boards.split(",") if b.strip()]

    if not board_ids:
        scheduler = BlockingScheduler()
        load_and_register_jobs(scheduler, _jobs_dir())
        return scheduler, []

    points_field = _load_env("PLANKA_POINTS_FIELD", "Points")
    interval = int(_load_env("PLANKA_POLL_INTERVAL", "60"))

    scheduler = BlockingScheduler()
    for board_id in board_ids:
        scheduler.add_job(
            _make_job(board_id, points_field),
            trigger=IntervalTrigger(seconds=interval),
            id=f"sync_points_{board_id}",
            name=f"List point totals — board {board_id}",
            max_instances=1,
            coalesce=True,
            next_run_time=__import__("datetime").datetime.now(),  # run immediately on start
        )

    load_and_register_jobs(scheduler, _jobs_dir())

    return scheduler, board_ids


def run_scheduler() -> None:
    """Start the blocking scheduler. Exits cleanly on SIGINT/SIGTERM."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    scheduler, board_ids = build_scheduler()

    discovered_jobs = [j for j in scheduler.get_jobs() if j.id.startswith("jobs_")]

    if not board_ids and not discovered_jobs:
        log.error(
            "No boards configured and no discovered jobs found. Set "
            "PLANKA_AUTOMATION_BOARDS in .env (comma-separated board IDs) or "
            "add a job script under jobs/Scheduled/."
        )
        sys.exit(1)

    points_field = _load_env("PLANKA_POINTS_FIELD", "Points")
    interval = int(_load_env("PLANKA_POLL_INTERVAL", "60"))

    log.info("Starting Planka automation scheduler")
    if board_ids:
        log.info("  Boards : %s", ", ".join(board_ids))
        log.info("  Field  : %s", points_field)
        log.info("  Interval: %ds", interval)
    if discovered_jobs:
        log.info("  Discovered jobs: %s", ", ".join(j.name for j in discovered_jobs))
    log.info("Press Ctrl+C to stop.")

    def _shutdown(signum, frame):
        log.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    scheduler.start()

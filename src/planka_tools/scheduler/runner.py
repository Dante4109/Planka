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
from apscheduler.triggers.interval import IntervalTrigger

from planka_tools.api.client import PlankaClient, PlankaError
from planka_tools.automations.list_points import sync_list_point_totals

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


def build_scheduler() -> tuple[BlockingScheduler, list[str]]:
    """Build and return a configured scheduler and the list of board IDs registered."""
    raw_boards = _load_env("PLANKA_AUTOMATION_BOARDS")
    board_ids = [b.strip() for b in raw_boards.split(",") if b.strip()]

    if not board_ids:
        return BlockingScheduler(), []

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

    return scheduler, board_ids


def run_scheduler() -> None:
    """Start the blocking scheduler. Exits cleanly on SIGINT/SIGTERM."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    scheduler, board_ids = build_scheduler()

    if not board_ids:
        log.error(
            "No boards configured. Set PLANKA_AUTOMATION_BOARDS in .env "
            "(comma-separated board IDs)."
        )
        sys.exit(1)

    points_field = _load_env("PLANKA_POINTS_FIELD", "Points")
    interval = int(_load_env("PLANKA_POLL_INTERVAL", "60"))

    log.info("Starting Planka automation scheduler")
    log.info("  Boards : %s", ", ".join(board_ids))
    log.info("  Field  : %s", points_field)
    log.info("  Interval: %ds", interval)
    log.info("Press Ctrl+C to stop.")

    def _shutdown(signum, frame):
        log.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    scheduler.start()

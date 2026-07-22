# Manual job test scripts

Small standalone scripts for running a job's `run()` function directly
against the live Planka instance, without waiting for its scheduled
trigger or a real webhook event.

Each script is piped into the `planka-webhook` container's Python over
stdin — no rebuild, no volume mount needed, and it uses the same
`planka_tools` package (and `.env` credentials) already running in that
container.

**⚠️ These run against your real, live Planka board — they will actually
move/copy/duplicate/assign cards. There is no dry-run mode.**

Run all commands from the repo root (`C:\projects\AppDev\Planka`).

---

## Scheduled jobs

```bash
# Move Tomorrow -> Today
docker exec -i planka-webhook python < scripts/jobs/scheduled/move_tomorrow_to_today.py

# Move This Month -> This Week
docker exec -i planka-webhook python < scripts/jobs/scheduled/move_this_month_to_this_week.py

# Sweep overdue cards -> Past-Due
docker exec -i planka-webhook python < scripts/jobs/scheduled/sweep_past_due.py

# Copy Daily (Personal board) -> Today (Daily Workflow board)
docker exec -i planka-webhook python < scripts/jobs/scheduled/copy_daily_to_today.py
```

## Webhook jobs

`auto_assign_in_progress` needs a real card ID (`CARD_ID` env var) —
it resolves that card's board and "In-Progress" list automatically, then
simulates a `cardUpdate` event moving the card there.

```bash
docker exec -i -e CARD_ID=<real-card-id> planka-webhook python < scripts/jobs/webhook/auto_assign_in_progress.py
```

Example:

```bash
docker exec -i -e CARD_ID=1803823947255383177 planka-webhook python < scripts/jobs/webhook/auto_assign_in_progress.py
```

---

## Adding a new manual test script

Copy the pattern from an existing scheduled script:

```python
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from planka_tools.api.client import PlankaClient
from planka_tools.jobs.Scheduled import <your_job_module> as job

with PlankaClient() as client:
    job.run(client)
```

Webhook jobs take `run(event, payload, client)` instead — build a
payload matching the real shape (`prevData`/`data` with `item.listId`,
`item.id`, `item.boardId`), like `auto_assign_in_progress.py` does.

---

## Viewing logs while jobs run for real

Two long-running containers run the job system automatically — both
defined in `docker-compose.yml`, both built from the local `Dockerfile`
(no volume mount, so a code change needs a rebuild — see
`docs/Restarting after code changes.md`):

| Container | What it runs | Fires on |
|---|---|---|
| `planka-scheduler` | `run_scheduler()` — registers all `jobs/Scheduled/*.py` with APScheduler | Their `TRIGGER` cron schedule |
| `planka-webhook` | Flask webhook server — dispatches `jobs/Webhook/*.py` | Real Planka webhook events |

`pt docker logs` only tails the `planka` app container, **not** either
of these — use plain `docker logs` directly:

```bash
# Follow scheduler logs live (job registration, each firing, errors)
docker logs -f planka-scheduler

# Follow webhook logs live (incoming events, job dispatch, errors)
docker logs -f planka-webhook

# Just the last N lines, no follow
docker logs --tail 100 planka-scheduler
docker logs --tail 100 planka-webhook
```

Both containers have `restart: unless-stopped`, so they come back up
automatically after a host/Docker restart — no manual `pt scheduler run`
needed anymore.

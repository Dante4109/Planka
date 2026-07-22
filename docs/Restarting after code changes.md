# Restarting after code changes

What you need to restart depends on which piece of Planka Tools you changed.
Both `planka-webhook` and `planka-scheduler` are containerized, built from
the local `Dockerfile` (`build: .` in `docker-compose.yml`). Neither has a
volume mount for `src/` — code is baked into the image via `COPY src/ src/`
at build time.

## Scheduler (`planka-scheduler` container)

Runs `run_scheduler()`, which discovers `jobs/Scheduled/*.py` and registers
each with APScheduler **once, at container start**.

- A plain `docker restart planka-scheduler` will **not** pick up code
  changes — it just restarts the existing image, and won't re-discover
  new/changed job files either (discovery only happens at startup, but
  restarting the container *does* re-run startup — so a restart alone is
  enough to pick up new/changed `jobs/Scheduled/*.py` files, since that's
  just data read from the image; it's *code* changes elsewhere in
  `planka_tools` that need a rebuild).
- To deploy a code change (not just a new job file already baked into a
  prior rebuild): **rebuild the image**:
  ```powershell
  docker compose up -d --build planka-scheduler
  ```

## Webhook (`planka-webhook` container)

- A plain `docker restart planka-webhook` will **not** pick up code
  changes — same reasoning as above.
- To deploy code changes: **rebuild the image**:
  ```powershell
  docker compose up -d --build planka-webhook
  ```
- Once the image has new code, no further restarts are needed for future
  job-file changes there: `load_webhook_jobs()` is called fresh on every
  incoming webhook event (inside `handle_event()`), not cached at startup.

## `.env`-only changes (e.g. `AUTO_ASSIGN_USER_ID`)

Read at runtime via `os.environ` / `_load_env()` — no rebuild needed.
Just:
```powershell
pt docker restart
```
(Per the existing COMMANDS.md tip: `restart`, not `stop`/`start`, so
`--force-recreate` reloads `.env`. Note: `pt docker restart` only
recreates the `planka` service — restart `planka-webhook`/
`planka-scheduler` directly with `docker restart <name>` or
`docker compose restart <name>` for their own `.env` changes.)

## Checking logs for the right container

`pt docker logs` only tails the **`planka`** app container
(`src/planka_tools/docker/commands.py` hardcodes `docker logs ... planka`).
It does not show `planka-webhook` or `planka-scheduler` output. Use plain
`docker logs` directly — see `scripts/jobs/README.md` for the full
log-viewing commands for both.

| Change | What to do |
|---|---|
| New/edited file in `jobs/Scheduled/` (image already has current `planka_tools` code) | `docker compose up -d --build planka-scheduler` (rebuild picks up the new file; a plain restart won't since it's not on a volume) |
| New/edited file in `jobs/Webhook/` | Rebuild+recreate: `docker compose up -d --build planka-webhook` |
| Any other `src/planka_tools/**` change | Rebuild whichever container(s) use that code — usually both |
| `.env` value change only | `docker compose restart planka-webhook planka-scheduler` (or `pt docker restart` for the `planka` service) |
| Want to see webhook/scheduler logs | `docker logs -f planka-webhook` / `docker logs -f planka-scheduler` (not `pt docker logs`) |

## Manually running a Scheduled job (skip waiting for the cron trigger)

See `scripts/jobs/README.md` — piping a small script into
`planka-webhook`'s Python over stdin runs any job's `run()` directly
against the live Planka instance, without waiting for its trigger.

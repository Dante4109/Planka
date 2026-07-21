# Planka Tools CLI — Command Reference

`planka_tools` is a Typer-based CLI installed as the `pt` command. It provides Docker management and automation helpers for your local Planka instance.

---

## Installation

From the Planka project root (`C:\projects\AppDev\Planka\`):

```powershell
pip install -e .
```

Verify the install:

```powershell
pt --help
```

---

## Top-Level Commands

```
pt docker     Manage the Planka Docker container
pt api        Query the Planka API
pt automation Run card automation rules
pt scheduler  Run and manage card automation schedules
pt webhook    Manage the Planka webhook receiver
```

---

## `pt docker` — Docker Management

All docker commands run `docker compose` from the Planka project directory automatically. You do **not** need to `cd` into the folder first.

### `pt docker start`
Start the Planka container.

```powershell
pt docker start
```

Equivalent to `docker compose up -d`.

---

### `pt docker stop`
Stop and remove the Planka container (volumes are preserved).

```powershell
pt docker stop
```

Equivalent to `docker compose down`.

---

### `pt docker restart`
Restart Planka and **reload `.env`** variables. Use this any time you edit `.env`.

```powershell
pt docker restart
```

> ⚠️ `docker compose restart` does **not** reload `.env`. This command uses `--force-recreate` to ensure all environment changes take effect.

---

### `pt docker logs`
Stream or snapshot Planka container logs.

```powershell
# Follow live logs (default, last 50 lines)
pt docker logs

# Show last 100 lines without following
pt docker logs --tail 100 --no-follow

# Short flags
pt docker logs -n 200 -F
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--tail` | `-n` | `50` | Number of recent lines to show |
| `--follow` / `--no-follow` | `-f` / `-F` | follow | Stream live output |

---

### `pt docker update`
Pull the latest Planka image and recreate the container.

```powershell
pt docker update
```

Runs `docker compose pull` then `docker compose up -d --force-recreate`.

---

### `pt docker backup`
Back up the Planka database and all Docker volumes to timestamped files.

```powershell
# Save backups to the default location (Planka project root / backups/)
pt docker backup

# Save to a custom directory
pt docker backup --output-dir D:\Backups\Planka
pt docker backup -o D:\Backups\Planka
```

**Output files (timestamped):**

| File | Contents |
|---|---|
| `planka_db_YYYYMMDD-HHMMSS.dump` | PostgreSQL database (custom format) |
| `planka_attachments_YYYYMMDD-HHMMSS.tar.gz` | Card attachments volume |
| `planka_user_avatars_YYYYMMDD-HHMMSS.tar.gz` | User avatar images volume |
| `planka_project_backgrounds_YYYYMMDD-HHMMSS.tar.gz` | Project background images volume |

**Restore database from backup:**

```powershell
pg_restore -U planka -h localhost -p 5432 -d planka -F c "backups\planka_db_YYYYMMDD-HHMMSS.dump"
```

---

### `pt docker reset-password`
Reset a Planka user's password. The password is prompted securely (not visible in shell history).

```powershell
# Prompts for password interactively
pt docker reset-password --username r3zadmin

# Pass password directly (less secure — visible in shell history)
pt docker reset-password --username r3zadmin --password "NewPassword123"
```

| Option | Short | Required | Description |
|---|---|---|---|
| `--username` | `-u` | ✅ | Planka username |
| `--password` | `-p` | prompted | New password (prompted if not provided) |

---

## `pt api` — API Queries

Talks directly to the Planka REST API. Reads credentials from `.env`.

### Setup — API credentials

Add one of the following to your `.env` file (see `.env.example` for reference):

```dotenv
# Option 1 — API key (preferred, no expiry)
# Create in Planka → click your avatar → Edit profile → API keys → Add API key
PLANKA_API_KEY=your_key_here

# Option 2 — Username + password (Bearer JWT)
PLANKA_USERNAME=r3zadmin
PLANKA_PASSWORD=your_password_here
```

---

### `pt api ping`
Test the API connection and show the authenticated user.

```powershell
pt api ping
# Connected as: Roger Zeller (r3zadmin)
# Role: admin
```

---

### `pt api list-projects`
List all projects visible to the authenticated user.

```powershell
pt api list-projects
#   [1357158568008091264] My Project
#   [1357158568008091265] Another Project
```

---

### `pt api list-boards`
List all boards in a project (use the ID from `list-projects`).

```powershell
pt api list-boards 1357158568008091264
#   [1357158568008091300] Main Board
#   [1357158568008091301] Archive
```

---

### `pt api list-cards`
List all cards on a board, with due dates where set.

```powershell
pt api list-cards 1357158568008091300
#   [1357158568008091400] Fix login bug | due: 2026-06-15
#   [1357158568008091401] Update README
```

---

## `pt automation` — Card Automations

### `pt automation sync-points`
Recompute list point totals on a board and update list titles immediately.

```powershell
# Update list titles live
pt automation sync-points 1784419684444013580

# Preview changes without writing anything
pt automation sync-points 1784419684444013580 --dry-run
```

---

## `pt scheduler` — Automation Schedules (polling fallback)

The scheduler uses APScheduler to poll Planka on a configurable interval. Use this as a fallback if the webhook server is not running.

### `pt scheduler run`
Start the automation scheduler (runs all configured card rules on their schedules).

```powershell
pt scheduler run
```

### `pt scheduler list`
List all configured automation schedules.

```powershell
pt scheduler list
```

---

## Job System — Custom Scheduled & Webhook Jobs

Beyond the built-in list-point-totals automation, you can drop in your own
job scripts and they'll be picked up automatically — no code changes to
`planka_tools` required.

**Directory layout:**

```
src/planka_tools/jobs/
  base.py          — contract documentation (read this first)
  loader.py         — auto-discovery (imports .py files, skips malformed ones)
  Scheduled/        — time-triggered jobs (APScheduler)
  Webhook/          — event-triggered jobs (Flask webhook receiver)
```

**Scheduled job contract** — a `.py` file under `jobs/Scheduled/` must define:

```python
TRIGGER = {"type": "cron", "hour": 8, "minute": 0}   # or {"type": "interval", "hours": 6}

def run(client: PlankaClient) -> None:
    ...
```

`TRIGGER["type"]` is `"cron"` or `"interval"`; the remaining keys are passed
straight through to APScheduler's `CronTrigger`/`IntervalTrigger`.

**Webhook job contract** — a `.py` file under `jobs/Webhook/` must define:

```python
EVENTS = ["cardUpdate"]   # Planka event names this job subscribes to

def run(event: str, payload: dict, client: PlankaClient) -> None:
    ...
```

**Adding a new job:**

1. Create a new `.py` file in `jobs/Scheduled/` or `jobs/Webhook/` following the contract above.
2. Restart `pt scheduler run` (for Scheduled jobs) or the webhook server (for Webhook jobs) to pick it up.
3. Run `pt scheduler list` to confirm it shows up, tagged `[discovered]`.

A malformed job file (missing `TRIGGER`/`EVENTS`/`run`, or an error at import
time) is logged and skipped — it never crashes the scheduler or webhook
server, and other jobs keep loading normally.

**Environment variables:**

| Variable | Purpose | Default |
|---|---|---|
| `AUTO_ASSIGN_USER_ID` | User ID assigned by the `auto_assign_in_progress` example job | none — job no-ops if unset |
| `JOBS_DIR` | Override the base jobs directory | `src/planka_tools/jobs/` |

**Security note:** job files are imported and executed as Python code. Only
put trusted scripts in `jobs/Scheduled/` and `jobs/Webhook/`.

---

## `pt webhook` — Webhook Receiver

Event-driven alternative to the polling scheduler. A lightweight Flask server receives Planka events and updates list titles instantly.

### Quick setup

1. Add `PLANKA_WEBHOOK_TOKEN` to your `.env` (generate a random secret).
2. Start the full stack:
   ```powershell
   pt docker start
   ```
   This brings up both Planka and the `planka-webhook` sidecar container.
3. Register the webhook URL with Planka (one-time):
   ```powershell
   pt webhook register
   ```

### `pt webhook start`
Start the webhook receiver server in the **foreground** (for local testing outside Docker).

```powershell
pt webhook start

# Override the port
pt webhook start --port 5002

# Enable Flask debug mode
pt webhook start --debug
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--port` | `-p` | `PLANKA_WEBHOOK_PORT` / `5001` | Port to listen on |
| `--debug` | | off | Flask debug mode |

> ℹ️ In production, the webhook server runs automatically as the `planka-webhook` Docker service. `pt webhook start` is for local development only.

---

### `pt webhook register`
Register the webhook URL with Planka so it starts sending events.

```powershell
# Register with defaults (points to planka-webhook container, all relevant events)
pt webhook register

# Custom URL (e.g., ngrok tunnel for testing)
pt webhook register --url https://abc123.ngrok.io/webhook

# Custom name
pt webhook register --name my-automation
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--url` | `-u` | `http://planka-webhook:5001/webhook` | Webhook receiver URL |
| `--name` | `-n` | `planka-tools` | Display name in Planka |
| `--events` | `-e` | see below | Comma-separated event list |

**Default events subscribed:**
```
customFieldValueUpdate,customFieldValueDelete,cardUpdate,cardDelete
```

---

### `pt webhook list`
List all webhooks registered in Planka.

```powershell
pt webhook list
#   [1234567890] planka-tools
#        URL: http://planka-webhook:5001/webhook
#     Events: customFieldValueUpdate,customFieldValueDelete,cardUpdate,cardDelete
```

---

### `pt webhook delete`
Remove a webhook registration from Planka.

```powershell
pt webhook delete 1234567890
```

---

## Tips

**Get help on any command:**
```powershell
pt --help
pt docker --help
pt docker backup --help
```

**After editing `.env`, always use `restart` not `stop`/`start`:**
```powershell
# WRONG — does not reload .env
pt docker stop
pt docker start

# CORRECT — reloads .env via --force-recreate
pt docker restart
```

**Access Planka:**
- Local: `http://localhost:1337`
- LAN:   `http://192.168.1.174:1337`

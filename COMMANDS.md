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
pt scheduler  Run and manage card automation schedules
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

## `pt scheduler` — Automation Schedules

> 🚧 Scheduler commands are stubs pending Phase 5 implementation (APScheduler integration).

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

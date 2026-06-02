# Planka — Docker Setup & Automation

Planka is an open-source kanban board deployed via Docker, connecting to a local PostgreSQL 16 instance. This repo also includes `planka_tools` — a Python CLI (`pt`) for Docker management, API access, and event-driven automations.

> 📋 **Full CLI reference:** See [COMMANDS.md](COMMANDS.md) for all `pt` commands.

## Prerequisites
- Docker Desktop 27.1+ running
- PostgreSQL 16 running (Windows service: `postgresql-x64-16`)
- Python 3.12+

---

## First-Time Setup

### 1. Create the database
```powershell
psql -U postgres -f setup-db.sql
```

### 2. Allow Docker subnet in PostgreSQL
Add one of the following lines to `C:\Program Files\PostgreSQL\16\data\pg_hba.conf`:
```
host    all    planka    172.17.0.0/16    scram-sha-256
```
Then reload PostgreSQL:
```powershell
Restart-Service postgresql-x64-16
```
> **Note:** The exact subnet depends on Docker Desktop. If the default `172.17.0.0/16` doesn't work,
> run `docker network inspect bridge` after Docker Desktop is running to find the actual subnet.

### 3. Configure environment
```powershell
Copy-Item .env.example .env
```
Edit `.env` and fill in:
- `DATABASE_URL` — your PostgreSQL connection string
- `SECRET_KEY_BASE` — random 128-char hex string
- `BASE_URL` — `http://<your-LAN-IP>:1337`
- `PLANKA_API_KEY` — create after first login (Profile → API keys)
- `PLANKA_WEBHOOK_TOKEN` — random secret for webhook auth

### 4. Install the `pt` CLI
```powershell
pip install -e .
```

### 5. Start Planka + webhook sidecar
```powershell
pt docker start
# or: docker compose up -d
```

### 6. Access Planka
- Local: http://localhost:1337
- LAN: http://192.168.1.174:1337

### 7. Register the webhook (one-time, after logging in and creating an API key)
```powershell
pt webhook register
```

---

## Daily Usage

Use the `pt` CLI — it handles all `docker compose` details automatically:

| Task | Command |
|------|---------|
| Start | `pt docker start` |
| Stop | `pt docker stop` |
| Restart + reload .env | `pt docker restart` |
| View logs | `pt docker logs` |
| Update Planka image | `pt docker update` |
| Backup DB + volumes | `pt docker backup` |
| Reset a user password | `pt docker reset-password --username r3zadmin` |

> ⚠️ Always use `pt docker restart` (not stop/start) when you edit `.env` — Docker's native restart does not reload env vars.

---

## Automation — List Point Totals

The automation watches a custom field named **Points** on your cards and keeps list titles in sync with the total points in each list.

**Title format:** `In-Progress (25)` — the number updates automatically whenever a card is added, moved, or edited.

### How it works

A Flask webhook server (`planka-webhook` Docker service) receives events from Planka the instant something changes — no polling delay.

```
Planka → POST /webhook → planka-webhook container → sync_list_point_totals → PATCH /api/lists/{id}
```

**Triggered by:**
| Event | When |
|---|---|
| `customFieldValueUpdate` | Points field set or changed on any card |
| `customFieldValueDelete` | Points field cleared |
| `cardUpdate` | Card moved to a different list |
| `cardDelete` | Card with points deleted |

### One-shot sync
```powershell
# Sync list titles for a board now
pt automation sync-points <board-id>

# Preview without writing
pt automation sync-points <board-id> --dry-run
```

### Webhook commands
```powershell
pt webhook register          # Register with Planka (one-time)
pt webhook list              # Show registered webhooks
pt webhook delete <id>       # Remove a webhook
pt webhook start             # Run server locally (dev/debug only)
```

### Polling fallback
If the webhook server is unavailable, the polling scheduler provides a backup:
```powershell
pt scheduler run    # Poll on PLANKA_POLL_INTERVAL (default: 60s)
```

---

## Updating Planka

```powershell
pt docker update
```

---

## Backup

```powershell
# Back up DB + all Docker volumes to ./backups/
pt docker backup

# Custom output directory
pt docker backup --output-dir D:\Backups\Planka
```

**Restore database from backup:**
```powershell
pg_restore -U planka -h localhost -p 5432 -d planka -F c "backups\planka_db_YYYYMMDD-HHMMSS.dump"
```

---

## Remote Access (Future)

When you're ready to access Planka away from home:

### Option A: Cloudflare Tunnel (Recommended — free, no port forwarding)
1. Create a Cloudflare account and add your domain
2. Install `cloudflared` and authenticate
3. Create a tunnel pointing to `http://localhost:1337`
4. Update `BASE_URL` in `.env` to your public domain, then restart: `pt docker restart`

### Option B: Tailscale (VPN mesh)
1. Install Tailscale on this machine and your remote devices
2. Access via Tailscale IP — no `BASE_URL` change needed for basic use

### Option C: Reverse Proxy + Port Forward
1. Set up Nginx or Caddy as a reverse proxy on this machine
2. Configure router to forward port 443 → this machine
3. Update `BASE_URL` in `.env` to your domain/DDNS address

---

## Migrating to a Hypervisor

1. **Copy the project folder** to the hypervisor (e.g., via SCP or USB)
2. **Set up PostgreSQL** on the hypervisor and run `setup-db.sql`
3. **Restore the database:**
   ```bash
   pg_restore -U planka -h localhost -d planka planka_backup_YYYYMMDD.dump
   ```
4. **Restore volumes** from tar backups
5. **Update `.env`:**
   - Change `DATABASE_URL` host to `host.docker.internal` (or new DB host)
   - Update `BASE_URL` to the new machine's IP or domain
6. **Start:** `pt docker start`

---

## Configuration Reference

All config lives in `.env`. See `.env.example` for a template with all variables documented.

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY_BASE` | Random 128-char hex string for session signing |
| `BASE_URL` | Public-facing URL (used in emails, links, WebSocket origin check) |
| `PLANKA_API_KEY` | API key for `pt` CLI (create in Planka → Profile → API keys) |
| `PLANKA_AUTOMATION_BOARDS` | Comma-separated board IDs to watch |
| `PLANKA_POINTS_FIELD` | Custom field name to sum (default: `Points`) |
| `PLANKA_POLL_INTERVAL` | Polling interval in seconds (default: `60`) |
| `PLANKA_WEBHOOK_TOKEN` | Bearer secret for webhook auth |
| `PLANKA_WEBHOOK_PORT` | Webhook server port (default: `5001`) |

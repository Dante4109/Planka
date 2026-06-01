# Planka — Docker Setup

Planka is an open-source kanban board deployed via Docker, connecting to a local PostgreSQL 16 instance.

> 📋 **CLI command reference:** See [COMMANDS.md](COMMANDS.md) for all `pt` commands (start, stop, backup, reset-password, etc.).

## Prerequisites
- Docker Desktop 27.1+ running
- PostgreSQL 16 running (Windows service: `postgresql-x64-16`)

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

### 3. Start Planka
```powershell
cd C:\projects\AppDev\Planka
docker compose up -d
```

### 4. Access Planka
- Local: http://localhost:1337
- LAN: http://192.168.0.4:1337

Complete the first-run setup to create your admin account.

---

## Daily Usage

| Task | Command |
|------|---------|
| Start | `docker compose up -d` |
| Stop  | `docker compose down` |
| View logs | `docker compose logs -f` |
| Restart | `docker compose restart` |

---

## Updating Planka

```powershell
docker compose pull
docker compose up -d
```

---

## Backup

### Database
```powershell
pg_dump -U planka -h localhost -d planka -F c -f planka_backup_$(Get-Date -Format 'yyyyMMdd').dump
```

### Uploaded Files (avatars, attachments, backgrounds)
```powershell
docker run --rm -v planka_attachments:/data -v ${PWD}:/backup alpine tar czf /backup/attachments_$(Get-Date -Format 'yyyyMMdd').tar.gz -C /data .
docker run --rm -v planka_user_avatars:/data -v ${PWD}:/backup alpine tar czf /backup/user-avatars_$(Get-Date -Format 'yyyyMMdd').tar.gz -C /data .
docker run --rm -v planka_project_backgrounds:/data -v ${PWD}:/backup alpine tar czf /backup/project-backgrounds_$(Get-Date -Format 'yyyyMMdd').tar.gz -C /data .
```

---

## Remote Access (Future)

When you're ready to access Planka away from home:

### Option A: Cloudflare Tunnel (Recommended — free, no port forwarding)
1. Create a Cloudflare account and add your domain
2. Install `cloudflared` and authenticate
3. Create a tunnel pointing to `http://localhost:1337`
4. Update `BASE_URL` in `.env` to your public domain, then restart: `docker compose restart`

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
6. **Start:** `docker compose up -d`

---

## Configuration Reference

All config lives in `.env`. See `.env.example` for a template.

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY_BASE` | Random 128-char hex string for session signing |
| `BASE_URL` | Public-facing URL (used in emails and links) |

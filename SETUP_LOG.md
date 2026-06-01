# Planka Setup Log

## Initial Setup — 2026-05-26

### Environment
- **Host OS:** Windows 11
- **Host LAN IP:** 192.168.1.174
- **Docker Desktop:** 27.1.1
- **PostgreSQL:** 16.4 (Windows service: `postgresql-x64-16`)
- **Planka Image:** `ghcr.io/plankanban/planka:latest`

---

### What Was Done

#### PostgreSQL
- Created dedicated `planka` role and `planka` database via `setup-db.sql`
- Added Docker subnet rules to `pg_hba.conf` to allow container connections:
  ```
  host    planka    planka    172.16.0.0/12      scram-sha-256
  host    planka    planka    192.168.65.0/24    scram-sha-256
  ```
- Container connects to host PostgreSQL via `host.docker.internal:5432`
- Applied config with `SELECT pg_reload_conf();` (no restart needed)

#### Docker
- Project files at: `C:\projects\AppDev\Planka\`
- Three named volumes created for persistence:
  - `planka_planka_attachments`
  - `planka_planka_user_avatars`
  - `planka_planka_project_backgrounds`
- Added Windows Firewall inbound rule: **Planka (1337)** — TCP port 1337, all profiles

#### Admin Account
- Username: `r3zadmin`
- Email: `rogerjohnmorellizeller@gmail.com`
- Role: `admin`
- Created via: `docker exec -it planka npm run db:create-admin-user`

---

### Issues Encountered & Fixes

#### Issue 1: Wrong LAN IP in BASE_URL
- Initially used `192.168.0.4` — incorrect
- Machine's actual Ethernet IP is `192.168.1.174`
- **Fix:** Updated `BASE_URL=http://192.168.1.174:1337` in `.env`

#### Issue 2: `docker compose restart` does NOT pick up `.env` changes
- `restart` only stops/starts the existing container — env vars are baked in at creation time
- **Fix:** Always use `docker compose up -d` or `docker compose up -d --force-recreate` after changing `.env`
- This caused WebSocket connections to fail because the container still had the old `BASE_URL`

#### Issue 3: WebSocket (Socket.io) failures after login
- Symptom: Login succeeds but app spins indefinitely; browser console shows:
  ```
  WebSocket connection to 'ws://192.168.1.174:1337/socket.io/...' failed
  ```
- Root cause: `BASE_URL` in the running container was stale (old IP), so Planka's `onlyAllowOrigins` rejected the WebSocket upgrade with HTTP 400
- **Fix:** `docker compose up -d --force-recreate` to reload environment variables

#### Issue 4: Admin password reset
- Admin account password was unknown after creation
- **Fix:** Reset via bcrypt hash generated inside the container:
  ```powershell
  docker exec planka node -e "const bcrypt = require('bcrypt'); bcrypt.hash('YOUR_PASSWORD', 10).then(h => console.log(h));"
  ```
  Then update in DB:
  ```sql
  UPDATE user_account SET password = '<bcrypt_hash>' WHERE username = 'r3zadmin';
  ```

---

### Key Commands

```powershell
# Start Planka
cd C:\projects\AppDev\Planka
docker compose up -d

# Stop Planka
docker compose down

# Restart (after .env changes — MUST use up, not restart)
docker compose up -d --force-recreate

# View live logs
docker logs -f planka

# Open a shell inside the container
docker exec -it planka sh

# Create a new admin user
docker exec -it planka npm run db:create-admin-user

# Reset a user password (generate hash first)
docker exec planka node -e "const bcrypt = require('bcrypt'); bcrypt.hash('NewPassword', 10).then(h => console.log(h));"
# Then run SQL:
# UPDATE user_account SET password = '<hash>' WHERE username = 'r3zadmin';
```

---

### Access URLs
| Context | URL |
|---|---|
| This machine | http://localhost:1337 |
| LAN (other devices) | http://192.168.1.174:1337 |

> **Important:** The URL you browse from must match `BASE_URL` in `.env`.
> If they differ, WebSocket connections will fail (HTTP 400) and the app will spin after login.

---

### Future: Remote Access
When ready to access from outside the home network, options include:
- **Cloudflare Tunnel** — free, no port forwarding required
- **Tailscale** — encrypted VPN mesh
- **Reverse proxy + port forward** — Nginx/Caddy + router rule

Steps when a domain is chosen:
1. Update `BASE_URL` in `.env` to the public domain (e.g., `https://planka.yourdomain.com`)
2. Run `docker compose up -d --force-recreate`

---

### Future: Migrating to a Hypervisor
1. Copy `C:\projects\AppDev\Planka\` to the new host
2. Run `setup-db.sql` on the target PostgreSQL instance
3. Restore DB: `pg_restore -U planka -d planka planka_backup.dump`
4. Export/import Docker volumes (see `README.md` for backup commands)
5. Update `BASE_URL` and `DATABASE_URL` in `.env`
6. `docker compose up -d`

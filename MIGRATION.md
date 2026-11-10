# Migrating planka-prod from Ubuntu to a Windows PC

Moves the prod stack (3 containers + host PostgreSQL) to a Windows machine. No VM.

- Prod today: `/opt/apps/Planka` on Ubuntu. Containers `planka`, `planka-webhook`, `planka-scheduler`.
- Database: PostgreSQL 18 on the host, reached through `DATABASE_URL`.
- Volumes: `planka_planka_attachments`, `planka_planka_project_backgrounds`, `planka_planka_user_avatars` (nearly empty).
- `BASE_URL`: `https://ubuntu-apps.swallow-draco.ts.net` (Tailscale).

Run the "Ubuntu" blocks on the old machine and the "Windows" blocks in PowerShell on the new one.

## Phase 0: Install on Windows (admin PowerShell)

```powershell
winget install Docker.DockerDesktop
winget install PostgreSQL.PostgreSQL.18     # must be 18: the dump is from PG 18 and PG 16 cannot restore it
winget install Tailscale.Tailscale
winget install Git.Git
```

- Reboot if Docker asks, then start Docker Desktop.
- Docker Desktop: Settings -> General -> "Start Docker Desktop when you sign in". Without it, `restart: unless-stopped` will not bring Planka back after a reboot.
- Set a password for the `postgres` user during the PostgreSQL install.

## Phase 1: Final backup (Ubuntu)

Stop the apps first so nothing writes new data, then dump.

```bash
cd /opt/apps/Planka && docker compose stop

mkdir -p ~/planka-migration && cd ~/planka-migration
set -a && . /opt/apps/Planka/.env && set +a
U=$(echo "$DATABASE_URL" | sed 's/@[^/]*\//@127.0.0.1:5432\//')
pg_dump -Fc "$U" -f planka.dump
pg_restore -l planka.dump | wc -l            # must print a non-zero number

for v in attachments project_backgrounds user_avatars; do
  docker run --rm -v planka_planka_$v:/v:ro -v "$PWD":/b alpine tar czf /b/$v.tgz -C /v .
done
cp /opt/apps/Planka/.env ~/planka-migration/env.backup
```

The `.tgz` files are root-owned: `sudo chown $USER: ~/planka-migration/*.tgz`.

## Phase 2: Transfer files

Ubuntu (replace `NEWPC` with the Windows machine's Tailscale name):

```bash
tailscale file cp ~/planka-migration/planka.dump ~/planka-migration/*.tgz ~/planka-migration/env.backup NEWPC:
git -C /opt/apps/Planka remote -v            # note the repo URL for Phase 4
```

Windows:

```powershell
mkdir C:\planka-migration
tailscale file get C:\planka-migration
```

## Phase 3: Restore PostgreSQL (Windows)

```powershell
$env:Path += ";C:\Program Files\PostgreSQL\18\bin"

psql -U postgres -h localhost -c "CREATE ROLE planka LOGIN PASSWORD 'NEW_PASSWORD_HERE';"
psql -U postgres -h localhost -c "CREATE DATABASE planka OWNER planka;"

# Connect as planka so restored objects are owned by it
pg_restore -U planka -h localhost -d planka --no-owner C:\planka-migration\planka.dump
psql -U planka -h localhost -d planka -c "\dt"
psql -U planka -h localhost -d planka -c "ANALYZE;"
```

Use a new password (the old one has appeared in terminal output). `setup-db.sql` in the repo does the same role/database creation.

Let the containers reach Postgres. Add to `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`:

```
host    planka    planka    172.16.0.0/12      scram-sha-256
host    planka    planka    192.168.65.0/24    scram-sha-256
```

Make sure `postgresql.conf` has `listen_addresses = '*'`, then:

```powershell
Restart-Service postgresql-x64-18
New-NetFirewallRule -DisplayName "Postgres from Docker" -Direction Inbound -Protocol TCP -LocalPort 5432 -RemoteAddress 172.16.0.0/12,192.168.65.0/24 -Action Allow
```

## Phase 4: App files (Windows)

The folder must be named `Planka`: Compose derives volume names from it (`planka_planka_attachments`, ...).

```powershell
mkdir C:\projects\AppDev; cd C:\projects\AppDev
git clone <REPO_URL> Planka
cd Planka
Copy-Item C:\planka-migration\env.backup .env
code .env      # UTF-8 without BOM; avoid Notepad
```

Edit `.env`:

```
DATABASE_URL=postgresql://planka:NEW_PASSWORD_HERE@host.docker.internal:5432/planka
```

Keep `SECRET_KEY_BASE`, `PLANKA_API_KEY`, `PLANKA_WEBHOOK_TOKEN` and `BASE_URL` unchanged for now.

Check `git -C /opt/apps/Planka status` on Ubuntu: any uncommitted local changes to compose files must be copied over too.

## Phase 5: Volumes and start (Windows)

```powershell
docker compose up --no-start        # builds images, creates empty volumes
foreach ($v in "attachments","project_backgrounds","user_avatars") {
  docker run --rm -v planka_planka_${v}:/v -v C:\planka-migration:/b alpine tar xzf /b/$v.tgz -C /v
}
docker compose up -d
docker compose ps
docker compose logs planka --tail 50
```

## Phase 6: Move the Tailscale address

Planka rejects WebSockets from any origin other than `BASE_URL`, so the URL and `BASE_URL` must match.

**Option A: keep the same URL (cleanest)**

Ubuntu:

```bash
tailscale serve reset
sudo tailscale set --hostname=ubuntu-apps-old
```

Windows:

```powershell
tailscale set --hostname=ubuntu-apps
tailscale serve --bg 1337
tailscale serve status
```

The name may get a `-1` suffix if the old node still holds it; check the status output. Compare with `tailscale serve status` on Ubuntu to match how HTTPS is served today.

**Option B: new URL**

Set `BASE_URL=https://<newhost>.swallow-draco.ts.net` in `.env`, then `docker compose up -d --force-recreate` (`restart` does not reload `.env`).

## Phase 7: Verify

1. Open the URL, log in as `r3zadmin`; check boards, cards and the "Points" custom fields.
2. `curl http://localhost:5001/health` answers from the webhook container.
3. `docker compose logs planka-scheduler --tail 20` shows polling with no auth errors.
4. Test the `pt` CLI; update its `BASE_URL` / `PLANKA_API_KEY` if it points at the old address.
5. Check Planka's webhook settings: webhooks stored in the DB may still point at the old host or port.
6. Reboot Windows once and confirm everything returns on its own.

## Phase 8: Retire the old machine

Keep `~/planka-migration` and the old Postgres untouched for a week or two. Then `docker compose down` in `/opt/apps/Planka`. Never use `down -v`; it deletes the volumes.

## Rollback

On Ubuntu: `cd /opt/apps/Planka && docker compose start`, and undo the Tailscale hostname change. Nothing on Ubuntu is deleted by this procedure.

## Faulty RAM: check the data

The data came off a machine with faulty RAM. After restoring:

```powershell
pg_amcheck -U postgres -h localhost -d planka --heapallindexed
```

The Ubuntu `pg_dump` completed without errors, which is a good sign, but the check is cheap.

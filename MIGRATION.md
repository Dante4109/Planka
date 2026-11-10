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

Received files may instead land in `%USERPROFILE%\Downloads` (the Tailscale tray app saves them there automatically). If `C:\planka-migration` is empty, look there and move them:

```powershell
Move-Item $HOME\Downloads\planka.dump, $HOME\Downloads\*.tgz, $HOME\Downloads\env.backup C:\planka-migration\
```

Use the PC's Tailscale name from `tailscale status` for `NEWPC` (this migration used `mephistopheles`). The trailing colon is required.

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

Use a new password (the old one has appeared in terminal output). If the password contains URL-reserved characters, see "Password with special characters" in Troubleshooting before putting it in `.env`.

If `psql` says `password authentication failed for user "postgres"`, you never set or forgot the superuser password. See "Reset the postgres superuser password" in Troubleshooting. `setup-db.sql` in the repo does the same role/database creation.

Let the containers reach Postgres. Add to `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`:

```
host    planka    planka    172.16.0.0/12      scram-sha-256
host    planka    planka    192.168.65.0/24    scram-sha-256
```

Docker Desktop connections appear to Postgres as coming from the PC's own LAN IP (here `192.168.1.201`), not from the Docker subnets. Add a rule for that address too (and give the PC a DHCP reservation in your router so it never changes):

```
host    planka    planka    192.168.1.201/32    scram-sha-256
```

Make sure `postgresql.conf` has `listen_addresses = '*'` (a separate file from `pg_hba.conf`), then:

```powershell
Restart-Service postgresql-x64-18      # can time out after an unclean stop; see Troubleshooting
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

The old URL points at `192.168.1.199` (the Ubuntu server). If you forget to change the host, the container connects to Ubuntu's Postgres and fails with `no pg_hba.conf entry for host "<windows IP>"`.

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

## Phase 8: Park the old machine

If you plan to move back (see "Switching back to the Ubuntu server"), leave the Ubuntu containers stopped (`docker compose stop`, not `down`) and keep `~/planka-migration` and the old Postgres untouched. If the move is permanent, wait a week or two, then `docker compose down` in `/opt/apps/Planka`. Never use `down -v`; it deletes the volumes.

## Rollback

On Ubuntu: `cd /opt/apps/Planka && docker compose start`, and undo the Tailscale hostname change. Nothing on Ubuntu is deleted by this procedure.

## Faulty RAM: check the data

The data came off a machine with faulty RAM. After restoring:

```powershell
pg_amcheck -U postgres -h localhost -d planka --heapallindexed
```

The Ubuntu `pg_dump` completed without errors, which is a good sign, but the check is cheap.

## Using it at home

Keep using the Tailscale URL on the LAN. Planka allows only one origin (`BASE_URL`) for its WebSocket, so `http://<LAN-IP>:1337` loads the page but login hangs. Tailscale connects devices on the same LAN directly (`tailscale ping <name>` shows the LAN address), so there is no internet round trip.

Give the Windows PC a DHCP reservation in the router: the `pg_hba.conf` rule for its LAN IP breaks if the address changes.

## Switching back to the Ubuntu server

Use this when the Ubuntu RAM is replaced. Run only one stack at a time: they have separate databases and would diverge.

1. **Test the Ubuntu hardware first.** Run memtest86+ (boot it from the GRUB menu or a USB stick) for at least one full pass, ideally overnight. Do not move back until it passes.

2. **Stop the Windows stack and dump its database (Windows):**
   ```powershell
   cd C:\projects\AppDev\Planka
   docker compose stop
   $env:Path += ";C:\Program Files\PostgreSQL\18\bin"
   pg_dump -U planka -h localhost -Fc -f C:\planka-migration\back.dump planka
   dir C:\planka-migration\back.dump
   ```

3. **Back up the Windows attachments/avatars/backgrounds volumes if you added any since the migration:**
   ```powershell
   foreach ($v in "attachments","project_backgrounds","user_avatars") {
     docker run --rm -v planka_planka_${v}:/v:ro -v C:\planka-migration:/b alpine tar czf /b/back-$v.tgz -C /v .
   }
   ```

4. **Send the files to Ubuntu (Windows):**
   ```powershell
   tailscale file cp C:\planka-migration\back.dump C:\planka-migration\back-attachments.tgz C:\planka-migration\back-project_backgrounds.tgz C:\planka-migration\back-user_avatars.tgz ubuntu-apps:
   ```
   (Use the Ubuntu node's current name from `tailscale status`, which may be `ubuntu-apps-old` if you renamed it.) On Ubuntu: `tailscale file get ~/planka-migration`, then check where the files landed (`~/Downloads` is common).

5. **Keep a safety copy of the old Ubuntu database, then restore (Ubuntu):**
   ```bash
   cd /opt/apps/Planka
   set -a && . ./.env && set +a
   U=$(echo "$DATABASE_URL" | sed 's/@[^/]*\//@127.0.0.1:5432\//')
   pg_dump -Fc "$U" -f ~/planka-migration/ubuntu-before-return.dump

   sudo -u postgres dropdb planka
   sudo -u postgres createdb -O planka planka
   pg_restore -d "$U" --no-owner ~/planka-migration/back.dump
   psql "$U" -c "SELECT count(*) FROM card;"
   ```
   Check that the card count looks right before continuing.

6. **Restore the volumes (Ubuntu):**
   ```bash
   for v in attachments project_backgrounds user_avatars; do
     docker run --rm -v planka_planka_$v:/v -v ~/planka-migration:/b alpine sh -c "cd /v && tar xzf /b/back-$v.tgz"
   done
   ```

7. **Fix the Tailscale hostname (Ubuntu).** The original name was `ubuntu-apps`. If you renamed it, rename it back:
   ```bash
   sudo tailscale set --hostname=ubuntu-apps
   tailscale serve status        # reapply serve if it was reset
   ```
   `BASE_URL` in `/opt/apps/Planka/.env` still points at `https://ubuntu-apps.swallow-draco.ts.net` and does not need to change.

8. **Start Ubuntu:**
   ```bash
   cd /opt/apps/Planka
   docker compose up -d --force-recreate
   docker compose ps
   ```
   Open `https://ubuntu-apps.swallow-draco.ts.net`, log in, and check recent edits made while you were on Windows.

9. **Park the Windows PC.** Leave it stopped (`docker compose stop`). Keep `back.dump` and `env.backup` until the Ubuntu server has run cleanly for a week or two. Update the `pt` CLI and any bookmarks that used the `mephistopheles` URL.

If Ubuntu fails to start with an unexpected error, you can run on Windows again: `docker compose start` there (nothing was deleted). Any edits made on Ubuntu after the restore would not be in the Windows database, so do not mix the two once Ubuntu has been used.

## Troubleshooting

### Docker engine not found

`failed to connect to the docker API at npipe:////./pipe/docker_engine` means Docker Desktop is not running. Start it and wait for "Engine running". If it won't start, check WSL 2 (`wsl --install`, reboot), BIOS virtualization, and membership of the `docker-users` group.

### `no configuration file provided: not found`

You are not in the repo folder. `cd C:\projects\AppDev\Planka` first.

### Reset the postgres superuser password

If the installer did not prompt for a password (a silent `winget` install) or you forgot it:

1. In an admin PowerShell, `notepad "C:\Program Files\PostgreSQL\18\data\pg_hba.conf"` and change the `127.0.0.1/32` and `::1/128` lines from `scram-sha-256` to `trust`.
2. `Restart-Service postgresql-x64-18`, then `psql -U postgres -h localhost -c "ALTER ROLE postgres PASSWORD 'NEW';"`.
3. Change both lines back to `scram-sha-256` and restart the service again. Leaving `trust` allows passwordless superuser access from this machine.

### `no pg_hba.conf entry for host "<IP>"` from the planka container

1. The IP in the message is what Postgres sees as the client. Add `host planka planka <IP>/32 scram-sha-256` to `pg_hba.conf`.
2. Reload and verify (works without restarting the service):
   ```powershell
   $env:Path += ";C:\Program Files\PostgreSQL\18\bin"
   psql -U postgres -h localhost -c "SELECT pg_reload_conf();"
   psql -U postgres -h localhost -c "SELECT line_number, address, netmask, user_name, error FROM pg_hba_file_rules WHERE database = '{planka}';"
   ```
   Every rule must appear with an empty `error` column.
3. If the rule is loaded and the error persists, check that `DATABASE_URL` host is `host.docker.internal`, not the old Ubuntu IP `192.168.1.199`. A connection to the wrong server produces the same message.
4. `docker compose restart` does not reload `.env`; use `docker compose up -d --force-recreate`.
5. `docker compose logs` keeps old output; use `--since 2m` or filter with `| Select-String "error:"`. PowerShell runs a pasted block top to bottom, so run checks after the restart, not in the same paste.

### Postgres service will not start / `postmaster.pid already exists`

After an unclean stop, crash recovery plus the data directory sync can take 90+ seconds on a slow disk, so `Restart-Service` reports a failure while Postgres is still recovering. Wait and run `Get-Service postgresql-x64-18`.

If it stays stopped, read the real error:

```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='PostgreSQL*'} -MaxEvents 5 | Format-List TimeCreated, Message
```

If it says `lock file "postmaster.pid" already exists`, an orphan process or a stale lock file is blocking the start:

```powershell
Get-Process postgres -ErrorAction SilentlyContinue      # any leftovers?
Stop-Process -Name postgres -Force                       # only if the service is stopped
Remove-Item "C:\Program Files\PostgreSQL\18\data\postmaster.pid"   # only if no postgres process is left
Start-Service postgresql-x64-18
```

An orphan server also keeps serving old configuration (it never re-read `pg_hba.conf`). Running `pg_ctl` or `postgres.exe` from an admin shell fails with "Execution of PostgreSQL by a user with administrative permissions is not permitted"; that is expected, use the service.

### Empty database after restore

`\dt` showing `Did not find any tables.` means the restore did not run. Stop the planka container, run `pg_restore -U planka -h localhost -d planka --no-owner C:\planka-migration\planka.dump`, then `psql ... -c "SELECT count(*) FROM card;"`. The `permission denied to analyze "pg_authid"` warnings from `ANALYZE;` as the `planka` role are harmless.

### `DATABASE_URL is not a valid connection string` / password with special characters

URL-reserved characters in the password must be percent-encoded in `DATABASE_URL`, but the Postgres role keeps the literal password:

```powershell
psql -U postgres -h localhost -c "ALTER ROLE planka PASSWORD 'Example00##';"
```
```
DATABASE_URL=postgresql://planka:Example00%23%23@host.docker.internal:5432/planka
```

| Character | Write as |
|---|---|
| `#` | `%23` |
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `?` | `%3F` |
| `%` | `%25` |
| space | `%20` |

No quotes or spaces around the value. A password of letters and digits avoids the problem. Edit `.env` with an editor that saves UTF-8 without a BOM (VS Code). Mask-check the line with:

```powershell
(Get-Content .env | Select-String '^DATABASE_URL') -replace '(?<=://[^:]+:)[^@]*(?=@)', '****'
```

### 502 Bad Gateway from the Tailscale URL

`tailscale serve` is working; the backend (planka on port 1337) is not answering. Check `docker compose ps` and `docker compose logs planka --since 2m`.

### Planka restarts in a loop

Always read the newest error: `docker compose logs planka --tail 60 | Select-String "error|FATAL|password|ECONN"`. Typical causes are in the sections above (`pg_hba.conf`, `DATABASE_URL`, empty database).

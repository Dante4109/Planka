import subprocess
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True)

# Resolve the Planka project root (two levels up from this file: src/planka_tools/docker/ -> project root)
PLANKA_DIR = Path(__file__).resolve().parents[3]


def _run(cmd: str, cwd: Path = PLANKA_DIR) -> None:
    """Run a shell command in the Planka project directory."""
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)


@app.command()
def start():
    """Start the Planka container (docker compose up -d)."""
    typer.echo("Starting Planka...")
    _run("docker compose up -d")
    typer.echo("Planka started.")


@app.command()
def stop():
    """Stop the Planka container (docker compose down)."""
    typer.echo("Stopping Planka...")
    _run("docker compose down")
    typer.echo("Planka stopped.")


@app.command()
def restart():
    """Restart Planka and reload environment variables (--force-recreate)."""
    typer.echo("Restarting Planka (force-recreate)...")
    _run("docker compose up -d --force-recreate")
    typer.echo("Planka restarted.")


@app.command()
def logs(
    tail: int = typer.Option(50, "--tail", "-n", help="Number of recent log lines to show."),
    follow: bool = typer.Option(True, "--follow/--no-follow", "-f/-F", help="Follow log output."),
):
    """Show Planka container logs."""
    follow_flag = "-f" if follow else ""
    _run(f"docker logs {follow_flag} --tail {tail} planka")


@app.command()
def update():
    """Pull the latest Planka image and recreate the container."""
    typer.echo("Pulling latest Planka image...")
    _run("docker compose pull")
    typer.echo("Recreating container...")
    _run("docker compose up -d --force-recreate")
    typer.echo("Planka updated.")


@app.command()
def backup(
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o",
        help="Directory to write backup files. Defaults to a 'backups/' folder in the Planka project root."
    )
):
    """
    Back up the Planka database and Docker volumes.

    Creates timestamped files:
      - planka_db_YYYYMMDD-HHMMSS.dump   (PostgreSQL custom format)
      - planka_attachments_YYYYMMDD-HHMMSS.tar.gz
      - planka_user_avatars_YYYYMMDD-HHMMSS.tar.gz
      - planka_project_backgrounds_YYYYMMDD-HHMMSS.tar.gz
    """
    backup_path = output_dir or (PLANKA_DIR / "backups")
    backup_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Load DB credentials from .env
    env_file = PLANKA_DIR / ".env"
    db_url = _read_env_var(env_file, "DATABASE_URL")
    if not db_url:
        typer.echo("ERROR: DATABASE_URL not found in .env", err=True)
        raise typer.Exit(1)

    # Parse DATABASE_URL: postgresql://user:password@host:port/dbname
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    db_host = parsed.hostname
    db_port = parsed.port or 5432
    db_user = parsed.username
    db_name = parsed.path.lstrip("/")
    db_pass = parsed.password

    # Database backup
    db_backup = backup_path / f"planka_db_{timestamp}.dump"
    typer.echo(f"Backing up database to {db_backup}...")
    env = os.environ.copy()
    env["PGPASSWORD"] = db_pass
    result = subprocess.run(
        f'pg_dump -U {db_user} -h {db_host} -p {db_port} -d {db_name} -F c -f "{db_backup}"',
        shell=True, env=env
    )
    if result.returncode != 0:
        typer.echo("ERROR: Database backup failed.", err=True)
        raise typer.Exit(1)
    typer.echo(f"  Database backup: {db_backup.name}")

    # Volume backups
    volumes = [
        ("planka_planka_attachments", "planka_attachments"),
        ("planka_planka_user_avatars", "planka_user_avatars"),
        ("planka_planka_project_backgrounds", "planka_project_backgrounds"),
    ]
    for volume_name, label in volumes:
        tar_file = backup_path / f"{label}_{timestamp}.tar.gz"
        typer.echo(f"Backing up volume '{volume_name}'...")
        _run(
            f'docker run --rm -v {volume_name}:/data -v "{backup_path}":/backup '
            f'alpine tar czf /backup/{tar_file.name} -C /data .'
        )
        typer.echo(f"  Volume backup: {tar_file.name}")

    typer.echo(f"\nAll backups saved to: {backup_path}")


@app.command(name="reset-password")
def reset_password(
    username: str = typer.Option(..., "--username", "-u", help="Planka username to reset."),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True,
                                  confirmation_prompt=True, help="New password."),
):
    """Reset a Planka user's password."""
    typer.echo(f"Generating bcrypt hash for '{username}'...")

    # Generate hash inside the container (bcrypt is available there)
    result = subprocess.run(
        f"docker exec planka node -e \"const bcrypt = require('bcrypt'); "
        f"bcrypt.hash('{password}', 10).then(h => console.log(h));\"",
        shell=True, capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        typer.echo("ERROR: Failed to generate bcrypt hash.", err=True)
        raise typer.Exit(1)

    bcrypt_hash = result.stdout.strip()

    # Update the DB
    env_file = PLANKA_DIR / ".env"
    db_url = _read_env_var(env_file, "DATABASE_URL")
    from urllib.parse import urlparse
    parsed = urlparse(db_url)

    env = os.environ.copy()
    env["PGPASSWORD"] = parsed.password

    sql = f"UPDATE user_account SET password = '{bcrypt_hash}' WHERE username = '{username}';"
    result = subprocess.run(
        f'psql -U {parsed.username} -h {parsed.hostname} -p {parsed.port or 5432} '
        f'-d {parsed.path.lstrip("/")} -c "{sql}"',
        shell=True, env=env, capture_output=True, text=True
    )
    if "UPDATE 1" in result.stdout:
        typer.echo(f"Password for '{username}' updated successfully.")
    elif "UPDATE 0" in result.stdout:
        typer.echo(f"WARNING: No user found with username '{username}'.", err=True)
        raise typer.Exit(1)
    else:
        typer.echo(f"ERROR: {result.stderr}", err=True)
        raise typer.Exit(1)


def _read_env_var(env_file: Path, key: str) -> Optional[str]:
    """Read a single variable from a .env file."""
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return None

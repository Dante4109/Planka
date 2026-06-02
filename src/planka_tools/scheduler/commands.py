import typer
from planka_tools.scheduler.runner import build_scheduler, run_scheduler, _load_env

app = typer.Typer(no_args_is_help=True)


@app.command()
def run():
    """Start the automation scheduler (polls all configured boards)."""
    run_scheduler()


@app.command(name="list")
def list_jobs():
    """List all configured automation schedules."""
    scheduler, board_ids = build_scheduler()

    if not board_ids:
        typer.echo(
            "No boards configured.\n"
            "Set PLANKA_AUTOMATION_BOARDS in .env (comma-separated board IDs)."
        )
        return

    points_field = _load_env("PLANKA_POINTS_FIELD", "Points")
    interval = int(_load_env("PLANKA_POLL_INTERVAL", "60"))

    typer.echo(f"Automation: List Point Totals")
    typer.echo(f"  Field    : {points_field}")
    typer.echo(f"  Interval : {interval}s")
    typer.echo(f"  Boards   :")
    for job in scheduler.get_jobs():
        typer.echo(f"    • {job.name}")


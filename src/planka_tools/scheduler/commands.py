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

    if board_ids:
        points_field = _load_env("PLANKA_POINTS_FIELD", "Points")
        interval = int(_load_env("PLANKA_POLL_INTERVAL", "60"))

        typer.echo(f"Automation: List Point Totals")
        typer.echo(f"  Field    : {points_field}")
        typer.echo(f"  Interval : {interval}s")
    else:
        typer.echo(
            "No boards configured.\n"
            "Set PLANKA_AUTOMATION_BOARDS in .env (comma-separated board IDs)."
        )

    jobs = scheduler.get_jobs()
    if not jobs:
        return

    typer.echo(f"  Jobs     :")
    for job in jobs:
        kind = "discovered" if job.id.startswith("jobs_") else "board-sync"
        typer.echo(f"    • [{kind}] {job.name}")


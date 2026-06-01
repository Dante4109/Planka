import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def run():
    """Start the automation scheduler (runs all configured card rules on their schedules)."""
    typer.echo("Scheduler not yet implemented. See src/planka_tools/scheduler/runner.py")


@app.command(name="list")
def list_jobs():
    """List all configured automation schedules."""
    typer.echo("Scheduler not yet implemented.")

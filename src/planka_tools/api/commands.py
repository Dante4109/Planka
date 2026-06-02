import typer
from planka_tools.api.client import PlankaClient, PlankaError

app = typer.Typer(no_args_is_help=True)


@app.command()
def ping():
    """Test the API connection and print the authenticated user."""
    try:
        with PlankaClient() as client:
            me = client.get_me()
            typer.echo(f"Connected as: {me.get('name', '?')} ({me.get('username', '?')})")
            typer.echo(f"Role: {me.get('role', '?')}")
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Connection error: {e}", err=True)
        raise typer.Exit(1)


@app.command(name="list-projects")
def list_projects():
    """List all visible Planka projects."""
    try:
        with PlankaClient() as client:
            projects = client.get_projects()
            if not projects:
                typer.echo("No projects found.")
                return
            for p in projects:
                typer.echo(f"  [{p['id']}] {p['name']}")
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)


@app.command(name="list-boards")
def list_boards(project_id: str = typer.Argument(..., help="Project ID")):
    """List all boards in a project."""
    try:
        with PlankaClient() as client:
            boards = client.get_project_boards(project_id)
            if not boards:
                typer.echo("No boards found.")
                return
            for b in boards:
                typer.echo(f"  [{b['id']}] {b['name']}")
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)


@app.command(name="list-cards")
def list_cards(board_id: str = typer.Argument(..., help="Board ID")):
    """List all cards on a board."""
    try:
        with PlankaClient() as client:
            cards = client.get_cards(board_id)
            if not cards:
                typer.echo("No cards found.")
                return
            for c in cards:
                due = f" | due: {c['dueDate'][:10]}" if c.get("dueDate") else ""
                typer.echo(f"  [{c['id']}] {c['name']}{due}")
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)

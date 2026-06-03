import typer
from pathlib import Path
from planka_tools.docker import commands as docker_commands
from planka_tools.scheduler import commands as scheduler_commands
from planka_tools.api import commands as api_commands
from planka_tools.automations import commands as automation_commands
from planka_tools.webhook import commands as webhook_commands
from planka_tools.export import commands as export_commands

app = typer.Typer(
    name="pt",
    help="Planka Tools — Docker management and automation CLI.",
    no_args_is_help=True,
)

app.add_typer(docker_commands.app, name="docker", help="Manage the Planka Docker container.")
app.add_typer(api_commands.app, name="api", help="Query the Planka API.")
app.add_typer(automation_commands.app, name="automation", help="Run card automation rules.")
app.add_typer(scheduler_commands.app, name="scheduler", help="Run and manage card automation schedules.")
app.add_typer(webhook_commands.app, name="webhook", help="Manage the Planka webhook receiver.")
app.add_typer(export_commands.app, name="export", help="Export board data to JSON.")
from planka_tools.board import commands as board_commands
app.add_typer(board_commands.app, name="board", help="Create or update boards from JSON templates.")


# Top-level aliases matching requested names
@app.command(name="CreateBoard")
def CreateBoard(project: str = typer.Option(..., "--Project", "-P", help="Project ID"), import_file: Path = typer.Option(..., "--Import", "-I", exists=True, help="JSON file to import")):
    """Alias: create a board from a JSON template (matches PT CreateBoard syntax)"""
    return board_commands.create_board(project=project, import_file=import_file)


@app.command(name="UpdateBoard")
def UpdateBoard(board: str = typer.Option(..., "--Board", "-B", help="Board ID"), import_file: Path = typer.Option(..., "--Import", "-I", exists=True, help="JSON file to import")):
    """Alias: update an existing board from a JSON template (matches PT UpdateBoard syntax)"""
    return board_commands.update_board(board=board, import_file=import_file)



def main():
    app()


if __name__ == "__main__":
    main()

import typer
from planka_tools.docker import commands as docker_commands
from planka_tools.scheduler import commands as scheduler_commands
from planka_tools.api import commands as api_commands

app = typer.Typer(
    name="pt",
    help="Planka Tools — Docker management and automation CLI.",
    no_args_is_help=True,
)

app.add_typer(docker_commands.app, name="docker", help="Manage the Planka Docker container.")
app.add_typer(api_commands.app, name="api", help="Query the Planka API.")
app.add_typer(scheduler_commands.app, name="scheduler", help="Run and manage card automation schedules.")


def main():
    app()


if __name__ == "__main__":
    main()

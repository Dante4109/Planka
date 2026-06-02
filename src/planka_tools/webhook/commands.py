import typer
from planka_tools.api.client import PlankaClient, PlankaError

app = typer.Typer(no_args_is_help=True)

_WEBHOOK_EVENTS = "customFieldValueUpdate,customFieldValueDelete,cardUpdate,cardDelete"


@app.command()
def start(
    port: int = typer.Option(None, "--port", "-p", help="Override PLANKA_WEBHOOK_PORT"),
    debug: bool = typer.Option(False, "--debug", help="Enable Flask debug mode"),
):
    """Start the webhook receiver server (foreground, Ctrl+C to stop)."""
    from planka_tools.webhook.server import run_server
    run_server(port=port, debug=debug)


@app.command()
def register(
    name: str = typer.Option("planka-tools", "--name", "-n", help="Webhook name"),
    url: str = typer.Option(
        "http://planka-webhook:5001/webhook",
        "--url",
        "-u",
        help="Webhook URL Planka will POST to",
    ),
    events: str = typer.Option(
        _WEBHOOK_EVENTS,
        "--events",
        "-e",
        help="Comma-separated list of events",
    ),
):
    """Register the webhook URL with Planka (requires admin credentials)."""
    try:
        with PlankaClient() as client:
            webhook = client.create_webhook(name=name, url=url, events=events)
            typer.echo(f"✅ Webhook registered: [{webhook['id']}] {webhook['name']}")
            typer.echo(f"   URL:    {webhook['url']}")
            typer.echo(f"   Events: {webhook['events']}")
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)


@app.command(name="list")
def list_webhooks():
    """List all webhooks registered in Planka."""
    try:
        with PlankaClient() as client:
            webhooks = client.get_webhooks()
            if not webhooks:
                typer.echo("No webhooks registered.")
                return
            for w in webhooks:
                typer.echo(f"  [{w['id']}] {w['name']}")
                typer.echo(f"       URL: {w['url']}")
                typer.echo(f"    Events: {w['events']}")
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def delete(
    webhook_id: str = typer.Argument(..., help="Webhook ID to delete"),
):
    """Delete a webhook registration from Planka."""
    try:
        with PlankaClient() as client:
            client.delete_webhook(webhook_id)
            typer.echo(f"🗑  Webhook {webhook_id} deleted.")
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)

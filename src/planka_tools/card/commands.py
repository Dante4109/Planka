"""
Card commands.

Commands:
  pt card move --card <card-id> --list <list-id>
"""

from __future__ import annotations

import logging

import typer

from planka_tools.api.client import PlankaClient, PlankaError

log = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True)


@app.command("move")
def move_card(
    card: str = typer.Option(..., "--card", "-c", help="ID of the card to move"),
    list_id: str = typer.Option(..., "--list", "-l", help="ID of the destination list"),
):
    """Move a card to a different list, on the same board or a different board."""
    log.info("Moving card %s to list %s", card, list_id)
    try:
        with PlankaClient() as client:
            moved = client.move_card(card, list_id)
    except PlankaError as e:
        log.exception("Failed to move card %s to list %s", card, list_id)
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        log.exception("Unexpected error moving card %s to list %s", card, list_id)
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(1)

    log.info("Moved card %s to list %s", card, list_id)
    typer.echo(f"Moved card {moved.get('id', card)} to list {moved.get('listId', list_id)}")

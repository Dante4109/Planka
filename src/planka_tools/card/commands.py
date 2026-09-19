"""
Card commands.

Commands:
  pt card move --card <card-id> --list <list-id>
  pt card list --list <list-id>
  pt card list --board <board-id>
  pt card copy --card <card-id> [--list <list-id>]
"""

from __future__ import annotations

import logging
from typing import Optional

import typer

from planka_tools.api.client import PlankaClient, PlankaError

log = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True)


def _position(item: dict) -> float:
    """Return item's position for sorting, treating missing/None as 0."""
    return item.get("position") or 0


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


@app.command("copy")
def copy_card(
    card: str = typer.Option(..., "--card", "-c", help="ID of the card to copy"),
    list_id: Optional[str] = typer.Option(
        None, "--list", "-l", help="ID of the list to place the copy in (defaults to the original card's list)"
    ),
):
    """Duplicate a card, optionally placing the copy in a different list."""
    log.info("Copying card %s%s", card, f" to list {list_id}" if list_id else "")
    try:
        with PlankaClient() as client:
            copied = client.duplicate_card(card)
            if list_id:
                copied = client.move_card(copied["id"], list_id)
    except PlankaError as e:
        log.exception("Failed to copy card %s", card)
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        log.exception("Unexpected error copying card %s", card)
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(1)

    log.info("Copied card %s to new card %s", card, copied.get("id"))
    typer.echo(f"Copied card {card} to new card {copied.get('id')} in list {copied.get('listId')}")


def _print_card_table(list_name: str, list_id: str, cards: list[dict]) -> None:
    """Print a table titled with the list name and id, showing Card #, Id, and Name."""
    headers = ("Card", "Id", "Name")
    rows = [(str(i), c.get("id", ""), c.get("name", "")) for i, c in enumerate(cards, start=1)]

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(row: tuple) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    typer.echo(f"\n{list_name} [{list_id}]")
    typer.echo(_fmt_row(headers))
    typer.echo("  ".join("-" * w for w in widths))
    if not rows:
        typer.echo("(no cards)")
    else:
        for row in rows:
            typer.echo(_fmt_row(row))


@app.command("list")
def list_cards(
    list_id: Optional[str] = typer.Option(None, "--list", "-l", help="ID of the list to show cards for"),
    board: Optional[str] = typer.Option(None, "--board", "-b", help="ID of the board to show cards for (one table per list)"),
):
    """List cards in a single list, or every list on a board."""
    if not list_id and not board:
        typer.echo("Error: provide either --list or --board", err=True)
        raise typer.Exit(1)
    if list_id and board:
        typer.echo("Error: provide only one of --list or --board, not both", err=True)
        raise typer.Exit(1)

    log.info("Listing cards for %s", f"list {list_id}" if list_id else f"board {board}")
    try:
        with PlankaClient() as client:
            if board:
                lists = sorted(client.get_lists(board), key=_position)
                cards_by_list: dict[str, list] = {}
                for c in client.get_cards(board):
                    cards_by_list.setdefault(c.get("listId"), []).append(c)
                for lst in lists:
                    list_cards_sorted = sorted(cards_by_list.get(lst["id"], []), key=_position)
                    _print_card_table(lst.get("name") or lst["id"], lst["id"], list_cards_sorted)
            else:
                lst = client.get_list(list_id)
                board_id = lst.get("boardId")
                all_cards = client.get_cards(board_id) if board_id else []
                list_cards_sorted = sorted(
                    (c for c in all_cards if c.get("listId") == list_id),
                    key=_position,
                )
                _print_card_table(lst.get("name") or list_id, list_id, list_cards_sorted)
    except PlankaError as e:
        log.exception("Failed to list cards")
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        log.exception("Unexpected error listing cards")
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(1)

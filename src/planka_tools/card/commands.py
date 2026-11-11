"""
Card commands.

Commands:
  pt card move --card <card-id> --list <list-id>
  pt card move-all [-p <proj>] [-b <board>] -l <list> [-p <proj>] [-b <board>] -l <list> [-c <card name>]...
      (first of each = source, second = destination; destination project/board default to the source's)
  pt card list --list <list-id>
  pt card list --board <board-id>
  pt card copy --card <card-id> [--list <list-id>]
"""

from __future__ import annotations

import logging
from typing import Optional

import typer

from planka_tools.api.client import PlankaClient, PlankaError
from planka_tools.automations.list_points import strip_points_suffix

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


class _LookupError(Exception):
    """A board or list reference could not be resolved to exactly one object."""


def _resolve_project(client: PlankaClient, ref: str) -> dict:
    """Resolve a project by id, or by (case-insensitive) name."""
    projects = client.get_projects()
    by_id = next((p for p in projects if p.get("id") == ref), None)
    if by_id:
        return by_id
    matches = [p for p in projects if (p.get("name") or "").casefold() == ref.casefold()]
    if not matches:
        raise _LookupError(f'project "{ref}" not found; provide a valid project name or project-id')
    if len(matches) > 1:
        ids = ", ".join(p["id"] for p in matches)
        raise _LookupError(f'project name "{ref}" is ambiguous (matches ids: {ids}); use the project-id')
    return matches[0]


def _resolve_board(client: PlankaClient, ref: str, project: Optional[str] = None) -> dict:
    """Resolve a board by id, or by (case-insensitive) name.

    Searches the given project (name or id), or every project when none is given.
    """
    if project:
        projects = [_resolve_project(client, project)]
    else:
        projects = client.get_projects()
    boards = [b for p in projects for b in client.get_project_boards(p["id"])]
    where = f' in project "{project}"' if project else ""
    by_id = next((b for b in boards if b.get("id") == ref), None)
    if by_id:
        return by_id
    matches = [b for b in boards if (b.get("name") or "").casefold() == ref.casefold()]
    if not matches:
        hint = ""
        if not project and any((p.get("name") or "").casefold() == ref.casefold() for p in projects):
            hint = f' ("{ref}" is a project name; pass it with --project and give the board name with --board)'
        raise _LookupError(
            f'board "{ref}" not found{where}; provide a valid board name or board-id{hint}'
        )
    if len(matches) > 1:
        ids = ", ".join(b["id"] for b in matches)
        raise _LookupError(
            f'board name "{ref}" is ambiguous (matches ids: {ids}); '
            f"use the board-id or narrow it with --project"
        )
    return matches[0]


def _resolve_list(client: PlankaClient, ref: str, board_id: Optional[str], flag: str) -> dict:
    """Resolve a list by id or name.

    With a board, `ref` is matched against that board's list ids and (point-suffix-stripped,
    case-insensitive) names. Without one, `ref` must be a list id.
    """
    if board_id is None:
        try:
            return client.get_list(ref)
        except PlankaError as e:
            raise _LookupError(
                f'list "{ref}" not found by id ({e}); provide a valid list-id, '
                f"or a list name together with the board option"
            )
    lists = client.get_lists(board_id)
    by_id = next((l for l in lists if l.get("id") == ref), None)
    if by_id:
        return by_id
    matches = [
        l for l in lists
        if l.get("name") and strip_points_suffix(l["name"]).casefold() == ref.casefold()
    ]
    if not matches:
        names = ", ".join(f'"{strip_points_suffix(l["name"])}"' for l in lists if l.get("name"))
        raise _LookupError(
            f'list "{ref}" not found on board {board_id} (for {flag}); '
            f"provide a valid list name or list-id. Lists on this board: {names or '(none)'}"
        )
    if len(matches) > 1:
        ids = ", ".join(l["id"] for l in matches)
        raise _LookupError(f'list name "{ref}" is ambiguous (matches ids: {ids}); use the list-id')
    return matches[0]


def _pair(values: Optional[list[str]], flag: str) -> tuple[Optional[str], Optional[str]]:
    """Split a repeatable option into (source, destination). A 3rd value is an error."""
    values = values or []
    if len(values) > 2:
        raise _LookupError(f"{flag} may be given at most twice (source, then destination)")
    return (values[0] if values else None, values[1] if len(values) > 1 else None)


def run_move_all(
    project: Optional[list[str]],
    board: Optional[list[str]],
    list_: Optional[list[str]],
    card: Optional[list[str]] = None,
) -> None:
    """Move every card in a source list (or only the named cards) to a destination list.

    Each argument holds up to two values: [source, destination]. Destination project and
    board default to the source's; the destination list is required. `card` limits the move to
    cards with those names (case-insensitive, exact) or ids; every one must be found. Echoes the result and
    raises typer.Exit(1) on any error. Shared by `move-all` and by shortcuts.
    """
    try:
        src_project, dest_project_arg = _pair(project, "--project")
        src_board_ref, dest_board_arg = _pair(board, "--board")
        src_list_ref, dest_list_ref = _pair(list_, "--list")
        if not src_list_ref:
            raise _LookupError("--list is required (the list whose cards are moved)")
        if not dest_list_ref:
            raise _LookupError(
                'a second --list is required (the destination list), '
                'e.g. --list "this month" --list "Done"'
            )
        dest_project = dest_project_arg or src_project

        log.info("Moving all cards from list %s to list %s", src_list_ref, dest_list_ref)
        with PlankaClient() as client:
            src_board_id = _resolve_board(client, src_board_ref, src_project)["id"] if src_board_ref else None
            src = _resolve_list(client, src_list_ref, src_board_id, "--list (source)")
            src_id = src["id"]
            src_board_id = src.get("boardId") or src_board_id

            # Destination board: explicit, else the source's board name re-resolved in a
            # different destination project, else the source board itself.
            if dest_board_arg:
                dest_board_id = _resolve_board(client, dest_board_arg, dest_project)["id"]
            elif dest_project_arg and dest_project_arg != src_project:
                if not src_board_ref:
                    raise _LookupError("a destination --project needs a --board to look in")
                dest_board_id = _resolve_board(client, src_board_ref, dest_project)["id"]
            else:
                dest_board_id = src_board_id

            # Always scoped to the destination board, so list ids from other boards are rejected.
            dest = _resolve_list(client, dest_list_ref, dest_board_id, "--list (destination)")
            dest_id = dest["id"]

            if dest_id == src_id:
                typer.echo("Error: source and destination lists are the same", err=True)
                raise typer.Exit(1)

            cards = sorted(
                (c for c in client.get_cards(src_board_id) if c.get("listId") == src_id),
                key=_position,
            )
            if card:
                wanted = [w.casefold() for w in card]
                missing = [
                    w for w in card
                    if not any(
                        (c.get("name") or "").casefold() == w.casefold() or c.get("id") == w
                        for c in cards
                    )
                ]
                if missing:
                    names = ", ".join(f'"{c.get("name")}"' for c in cards if c.get("name"))
                    raise _LookupError(
                        f"card(s) not found in source list: {', '.join(repr(m) for m in missing)}. "
                        f"Cards in this list: {names or '(none)'}"
                    )
                cards = [
                    c for c in cards
                    if (c.get("name") or "").casefold() in wanted or c.get("id") in card
                ]
            if not cards:
                typer.echo(f"No cards in list {src_id}; nothing to move")
                return

            # Append after existing cards in the destination, preserving source order.
            existing = [c for c in client.get_cards(dest_board_id) if c.get("listId") == dest_id]
            base = max((_position(c) for c in existing), default=0)

            for i, c in enumerate(cards, start=1):
                client.move_card(c["id"], dest_id, position=base + i * 65536.0)
                log.info("Moved card %s to list %s", c["id"], dest_id)
    except typer.Exit:
        raise
    except _LookupError as e:
        log.error("Lookup failed: %s", e)
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except PlankaError as e:
        log.exception("Failed to move cards")
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        log.exception("Unexpected error moving cards")
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Moved {len(cards)} card(s) from list {src_id} to list {dest_id}")


@app.command("move-all")
def move_all_cards(
    project: Optional[list[str]] = typer.Option(
        None, "--project", "-p",
        help="Project name or ID. First = source, second = destination (default: the source's).",
    ),
    board: Optional[list[str]] = typer.Option(
        None, "--board", "-b",
        help="Board name or ID. First = source, second = destination (default: the source's).",
    ),
    list_: Optional[list[str]] = typer.Option(
        None, "--list", "-l",
        help="List name or ID. First = source, second = destination (both required).",
    ),
    card: Optional[list[str]] = typer.Option(
        None, "--card", "-c",
        help="Only move cards with this name (or ID). Repeatable; default: all cards in the list.",
    ),
):
    """Move every card in a list (or only cards matching --card) to another list.

    --project, --board and --list can each be given twice: the first is the source, the
    second the destination. Project and board left out of the destination are taken from
    the source; the destination --list is always required.

    \b
    pt card move-all -p "Proj" -b "Board" -l "this month" -l "Done"
    pt card move-all -p "Proj" -b "Board" -l "this month" -b "Other board" -l "Done"
    pt card move-all -p "Proj" -b "Board" -l "this month" -l "Done" -c "Write report"
    """
    run_move_all(project, board, list_, card)


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

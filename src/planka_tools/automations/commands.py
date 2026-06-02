import typer
from typing import Optional
from planka_tools.api.client import PlankaClient, PlankaError
from planka_tools.automations.list_points import sync_list_point_totals

app = typer.Typer(no_args_is_help=True)


@app.command(name="sync-points")
def sync_points(
    board_id: str = typer.Argument(..., help="Board ID to sync point totals on."),
    field_name: str = typer.Option("Points", "--field", "-f",
                                   help="Name of the custom field to sum."),
    dry_run: bool = typer.Option(False, "--dry-run", "-n",
                                 help="Show what would change without updating."),
):
    """
    Sync list titles with total card points on a board.

    List names are updated to include the sum of the 'Points' custom field
    across all non-closed cards in each list.

    Example:  "In-Progress"  →  "In-Progress (25)"
    """
    try:
        if dry_run:
            typer.echo(f"[dry-run] Checking board {board_id}...")
            _dry_run_sync(board_id, field_name)
        else:
            with PlankaClient() as client:
                changes = sync_list_point_totals(client, board_id, field_name)
            if changes:
                for c in changes:
                    typer.echo(f"  ✓ '{c.old_name}'  →  '{c.new_name}'  (total: {_fmt(c.total)})")
            else:
                typer.echo("All list titles are already up to date.")
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)


def _dry_run_sync(board_id: str, field_name: str) -> None:
    """Preview changes without writing to the API."""
    from planka_tools.automations.list_points import _POINTS_SUFFIX
    import re

    with PlankaClient() as client:
        resp = client._get(f"/api/boards/{board_id}")
        included = resp.get("included", {})

    custom_fields = included.get("customFields", [])
    points_field = next((f for f in custom_fields if f["name"] == field_name), None)
    if not points_field:
        typer.echo(f"  No '{field_name}' custom field found on this board.")
        return

    points_field_id = points_field["id"]
    card_to_list = {
        c["id"]: c["listId"]
        for c in included.get("cards", [])
        if not c.get("isClosed")
    }
    list_totals: dict[str, float] = {}
    for val in included.get("customFieldValues", []):
        if val["customFieldId"] != points_field_id:
            continue
        list_id = card_to_list.get(val["cardId"])
        if list_id is None:
            continue
        try:
            list_totals[list_id] = list_totals.get(list_id, 0.0) + float(val["content"])
        except (ValueError, TypeError):
            pass

    any_change = False
    for lst in included.get("lists", []):
        current = lst.get("name") or ""
        base = _POINTS_SUFFIX.sub("", current).strip()
        total = list_totals.get(lst["id"], 0.0)
        new = f"{base} ({_fmt(total)})" if total > 0 else base
        if new != current:
            typer.echo(f"  would update: '{current}'  →  '{new}'")
            any_change = True

    if not any_change:
        typer.echo("  No changes needed.")


def _fmt(total: float) -> str:
    return str(int(total)) if total == int(total) else str(round(total, 2))

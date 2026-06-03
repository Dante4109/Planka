"""
Export commands for planka_tools.

Usage:
  pt export --board <board-id> [--cards] [--output file.json]

Also supports short forms used in examples: `pt export -Cards True -Board <BoardId>`
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from planka_tools.api.client import PlankaClient, PlankaError

app = typer.Typer(invoke_without_command=True, no_args_is_help=True, help="Export board data to JSON")


@app.callback(invoke_without_command=True)
def export_board(
    board: str = typer.Option(..., "--board", "-b", help="Board ID to export"),
    cards: bool = typer.Option(False, "--cards", "-c", help="Include cards in the export"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file path"),
):
    """Export lists, labels, custom fields (and optionally cards) from a board to JSON."""
    try:
        with PlankaClient() as client:
            resp = client.get_board_included(board)
    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Connection error: {e}", err=True)
        raise typer.Exit(1)

    included = resp.get("included", {})
    result: dict = {
        "board": resp.get("item", {}),
        "lists": included.get("lists", []),
        "labels": included.get("labels", []),
        "customFieldGroups": included.get("customFieldGroups", []),
        "customFields": included.get("customFields", []),
        "customFieldValues": included.get("customFieldValues", []),
    }

    if cards:
        result["cards"] = included.get("cards", [])

    # Determine output filename
    if output:
        out_path = Path(output)
    else:
        out_path = Path.cwd() / f"board_{board}_export.json"

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        typer.echo(f"Failed to write output file: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Export written to: {out_path}")

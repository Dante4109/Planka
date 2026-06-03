"""
Board template import/export commands.

Commands:
  pt board create --project <project-id> --import <file.json>
  pt board update --board <board-id> --import <file.json>

Top-level aliases also provided: pt createboard and pt updateboard
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import typer

from planka_tools.api.client import PlankaClient, PlankaError

app = typer.Typer(no_args_is_help=True)


def _strip_id(obj: dict) -> dict:
    """Return a shallow copy of obj without id fields that shouldn't be sent on create."""
    return {k: v for k, v in obj.items() if k not in ("id", "boardId", "listId", "cardId", "groupId")}


@app.command("create")
def create_board(
    project: str = typer.Option(..., "--project", "-p", help="Project ID to create board in"),
    import_file: Path = typer.Option(..., "--import", "-i", exists=True, help="JSON file produced by pt export"),
):
    """Create a new board from the supplied JSON template file."""
    data = json.loads(import_file.read_text(encoding="utf-8"))
    board_item = data.get("board", {})
    board_name = board_item.get("name") or f"Imported board"

    try:
        with PlankaClient() as client:
            new_board = client.create_board(project, name=board_name)
            board_id = new_board["id"]
            typer.echo(f"Created board {board_name} [{board_id}]")

            # Labels
            existing_labels = {l["name"]: l for l in client.get_labels(board_id)}
            for lbl in data.get("labels", []):
                if lbl["name"] in existing_labels:
                    typer.echo(f"Label exists, skipping: {lbl['name']}")
                    continue
                payload = _strip_id(lbl)
                payload.setdefault("color", payload.get("color", "berry-red"))
                created = client.create_label(board_id, name=payload.get("name"), color=payload.get("color"))
                typer.echo(f"  Created label: {created['name']} [{created['id']}]")

            # Custom field groups
            group_map: Dict[str, str] = {}
            for grp in data.get("customFieldGroups", []):
                payload = _strip_id(grp)
                # Create via API
                try:
                    created = client._post(f"/api/boards/{board_id}/custom-field-groups", json=payload)["item"]
                    group_map[grp.get("id")] = created["id"]
                    typer.echo(f"  Created custom field group: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create group {grp.get('name')}: {e}")

            # Custom fields
            for fld in data.get("customFields", []):
                payload = _strip_id(fld)
                # Map groupId if present
                old_gid = fld.get("groupId")
                if old_gid and old_gid in group_map:
                    payload["groupId"] = group_map[old_gid]
                try:
                    created = client._post(f"/api/boards/{board_id}/custom-fields", json=payload)["item"]
                    typer.echo(f"  Created custom field: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create custom field {fld.get('name')}: {e}")

            # Lists
            list_map: Dict[str, str] = {}
            for lst in data.get("lists", []):
                payload = _strip_id(lst)
                created = client.create_list(board_id, name=payload.get("name", ""), position=payload.get("position", 65536.0))
                list_map[lst.get("id")] = created["id"]
                typer.echo(f"  Created list: {created['name']} [{created['id']}]")

            # Cards (optional)
            for c in data.get("cards", []):
                src_list_id = c.get("listId")
                target_list_id = list_map.get(src_list_id)
                if not target_list_id:
                    typer.echo(f"  Skipping card (list missing): {c.get('name')}")
                    continue
                payload = _strip_id(c)
                created = client.create_card(target_list_id, name=payload.get("name", ""), position=payload.get("position", 65536.0), description=payload.get("description"))
                typer.echo(f"  Created card: {created['name']} [{created['id']}] in list {target_list_id}")

    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)


@app.command("update")
def update_board(
    board: str = typer.Option(..., "--board", "-b", help="Board ID to update"),
    import_file: Path = typer.Option(..., "--import", "-i", exists=True, help="JSON file produced by pt export"),
):
    """Update an existing board by adding missing lists, labels, custom fields, and cards (no deletions)."""
    data = json.loads(import_file.read_text(encoding="utf-8"))

    try:
        with PlankaClient() as client:
            included = client.get_board_included(board).get("included", {})

            # Existing maps by name
            existing_lists = {l["name"]: l for l in included.get("lists", [])}
            existing_labels = {l["name"]: l for l in included.get("labels", [])}
            existing_groups = {g["name"]: g for g in included.get("customFieldGroups", [])}
            existing_fields = {f["name"]: f for f in included.get("customFields", [])}

            # Create labels
            for lbl in data.get("labels", []):
                if lbl["name"] in existing_labels:
                    typer.echo(f"Label exists, skipping: {lbl['name']}")
                    continue
                payload = _strip_id(lbl)
                payload.setdefault("color", payload.get("color", "berry-red"))
                created = client.create_label(board, name=payload.get("name"), color=payload.get("color"))
                typer.echo(f"  Created label: {created['name']} [{created['id']}]")

            # Create groups
            group_map: Dict[str, str] = {}
            for grp in data.get("customFieldGroups", []):
                if grp.get("name") in existing_groups:
                    group_map[grp.get("id")] = existing_groups[grp.get("name")]["id"]
                    typer.echo(f"Custom field group exists, skipping: {grp['name']}")
                    continue
                try:
                    payload = _strip_id(grp)
                    created = client._post(f"/api/boards/{board}/custom-field-groups", json=payload)["item"]
                    group_map[grp.get("id")] = created["id"]
                    typer.echo(f"  Created custom field group: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create group {grp.get('name')}: {e}")

            # Create fields
            for fld in data.get("customFields", []):
                if fld.get("name") in existing_fields:
                    typer.echo(f"Custom field exists, skipping: {fld['name']}")
                    continue
                payload = _strip_id(fld)
                old_gid = fld.get("groupId")
                if old_gid and old_gid in group_map:
                    payload["groupId"] = group_map[old_gid]
                try:
                    created = client._post(f"/api/boards/{board}/custom-fields", json=payload)["item"]
                    typer.echo(f"  Created custom field: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create custom field {fld.get('name')}: {e}")

            # Create lists
            list_map: Dict[str, str] = {}
            for lst in data.get("lists", []):
                if lst.get("name") in existing_lists:
                    existing = existing_lists[lst.get("name")]
                    list_map[lst.get("id")] = existing["id"]
                    typer.echo(f"List exists, skipping: {lst['name']}")
                    continue
                payload = _strip_id(lst)
                created = client.create_list(board, name=payload.get("name", ""), position=payload.get("position", 65536.0))
                list_map[lst.get("id")] = created["id"]
                typer.echo(f"  Created list: {created['name']} [{created['id']}]")

            # Refresh included (to include newly created lists)
            included = client.get_board_included(board).get("included", {})
            # Cards: only create if name not present in target list
            cards_existing = included.get("cards", [])
            cards_by_list_name = {}
            for c in cards_existing:
                cards_by_list_name.setdefault(c.get("listId"), set()).add(c.get("name"))

            for c in data.get("cards", []):
                src_list_id = c.get("listId")
                target_list_id = list_map.get(src_list_id) or existing_lists.get(next((l["name"] for l in data.get("lists", []) if l.get("id")==src_list_id), ""), {}).get("id")
                if not target_list_id:
                    typer.echo(f"  Skipping card (list missing): {c.get('name')}")
                    continue
                existing_names = cards_by_list_name.get(target_list_id, set())
                if c.get("name") in existing_names:
                    typer.echo(f"  Card exists in list, skipping: {c.get('name')}")
                    continue
                payload = _strip_id(c)
                created = client.create_card(target_list_id, name=payload.get("name", ""), position=payload.get("position", 65536.0), description=payload.get("description"))
                typer.echo(f"  Created card: {created['name']} [{created['id']}] in list {target_list_id}")

    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)


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
    """Return a shallow copy of obj without id fields that shouldn't be sent on create.

    Also strip the export-specific customFieldGroupId so new groups/fields aren't bound to old IDs.
    """
    return {k: v for k, v in obj.items() if k not in ("id", "boardId", "listId", "cardId", "groupId", "customFieldGroupId")}


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
            label_map: Dict[str, str] = {}
            for lbl in data.get("labels", []):
                old_id = lbl.get("id")
                name = lbl.get("name")
                if name in existing_labels:
                    existing = existing_labels[name]
                    label_map[old_id] = existing["id"]
                    typer.echo(f"Label exists, skipping: {name}")
                    continue
                payload = _strip_id(lbl)
                payload.setdefault("color", payload.get("color", "berry-red"))
                created = client.create_label(board_id, name=payload.get("name"), color=payload.get("color"))
                label_map[old_id] = created["id"]
                typer.echo(f"  Created label: {created['name']} [{created['id']}]")

            # Custom field groups
            group_map: Dict[str, str] = {}
            for grp in data.get("customFieldGroups", []):
                try:
                    payload = {"name": grp.get("name"), "position": grp.get("position", 65536.0)}
                    created = client._post(f"/api/boards/{board_id}/custom-field-groups", json=payload)["item"]
                    group_map[grp.get("id")] = created["id"]
                    typer.echo(f"  Created custom field group: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create group {grp.get('name')}: {e}")

            # Custom fields
            field_map: Dict[str, str] = {}  # old field id -> new field id
            for fld in data.get("customFields", []):
                old_gid = fld.get("customFieldGroupId") or fld.get("groupId")
                new_gid = group_map.get(old_gid) if old_gid else None
                if not new_gid:
                    typer.echo(f"  Skipping custom field {fld.get('name')}: no matching group found")
                    continue
                payload = {"name": fld.get("name"), "position": fld.get("position", 65536.0)}
                if fld.get("showOnFrontOfCard") is not None:
                    payload["showOnFrontOfCard"] = bool(fld.get("showOnFrontOfCard"))
                try:
                    created = client._post(f"/api/custom-field-groups/{new_gid}/custom-fields", json=payload)["item"]
                    field_map[fld.get("id")] = created["id"]
                    typer.echo(f"  Created custom field: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create custom field {fld.get('name')}: {e}")


            # Lists
            list_map: Dict[str, str] = {}
            for lst in data.get("lists", []):
                # Skip system lists or entries without a valid name
                lst_name = lst.get("name")
                if not lst_name:
                    typer.echo(f"  Skipping unnamed/system list with id {lst.get('id')}")
                    continue
                try:
                    create_payload: dict = {"name": lst_name, "position": lst.get("position", 65536.0)}
                    if lst.get("type"):
                        create_payload["type"] = lst.get("type")
                    if lst.get("color"):
                        create_payload["color"] = lst.get("color")
                    created = client._post(f"/api/boards/{board_id}/lists", json=create_payload)["item"]
                    list_map[lst.get("id")] = created["id"]
                    typer.echo(f"  Created list: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create list {lst_name}: {e}")

            # Cards (optional)
            # Build card->label mapping if the export contains such relations
            card_label_map: Dict[str, list] = {}
            for key in ("cardLabels", "card_label", "cardsLabels", "cardLabelRelations", "cards_label"):
                for rel in data.get(key, []):
                    if rel.get("cardId") and rel.get("labelId"):
                        card_label_map.setdefault(rel["cardId"], []).append(rel["labelId"])

            me = client.get_me()
            my_id = me.get("id") if me else None

            for c in data.get("cards", []):
                src_list_id = c.get("listId")
                target_list_id = list_map.get(src_list_id)
                if not target_list_id:
                    typer.echo(f"  Skipping card (list missing): {c.get('name')}")
                    continue
                payload = _strip_id(c)
                try:
                    create_payload = {"name": payload.get("name", ""), "position": payload.get("position", 65536.0), "description": payload.get("description")}
                    typer.echo(f"    Creating card payload: {create_payload} in list {target_list_id}")
                    created = client.create_card(target_list_id, name=create_payload["name"], position=create_payload["position"], description=create_payload.get("description"))
                    typer.echo(f"  Created card: {created['name']} [{created['id']}] in list {target_list_id}")

                    # Attach labels — prefer embedded labelIds on card, fall back to top-level cardLabels map
                    old_card_id = c.get("id")
                    embedded_label_ids = c.get("labelIds") or []
                    relation_label_ids = card_label_map.get(old_card_id, [])
                    old_label_ids = embedded_label_ids if embedded_label_ids else relation_label_ids
                    for old_label_id in old_label_ids:
                        new_label_id = label_map.get(old_label_id)
                        if new_label_id:
                            try:
                                client.add_label_to_card(created["id"], new_label_id)
                                typer.echo(f"    Attached label {new_label_id} to card {created['id']}")
                            except Exception as e:
                                typer.echo(f"    Failed to attach label {new_label_id} to card {created['id']}: {e}")

                    # Ensure new cards are not auto-assigned to the current user
                    if my_id:
                        try:
                            client.remove_member_from_card(created["id"], my_id)
                            typer.echo(f"    Removed auto-assigned member {my_id} from card {created['id']}")
                        except Exception:
                            # Not all servers assign or allow removal; ignore failures
                            pass

                    # Set custom field values
                    for fv in c.get("customFieldValues", []):
                        old_gid = fv.get("customFieldGroupId")
                        old_fid = fv.get("customFieldId")
                        new_gid = group_map.get(old_gid)
                        new_fid = field_map.get(old_fid)
                        if new_gid and new_fid and fv.get("content"):
                            try:
                                client.set_custom_field_value(created["id"], new_gid, new_fid, fv["content"])
                                typer.echo(f"    Set custom field value [{fv['content']}] on card {created['id']}")
                            except Exception as e:
                                typer.echo(f"    Failed to set custom field value on card {created['id']}: {e}")

                except Exception as e:
                    typer.echo(f"  Failed to create card {c.get('name')}: {e} -- payload: {create_payload}")

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
            label_map: Dict[str, str] = {}
            for lbl in data.get("labels", []):
                old_id = lbl.get("id")
                name = lbl.get("name")
                if name in existing_labels:
                    label_map[old_id] = existing_labels[name]["id"]
                    typer.echo(f"Label exists, skipping: {name}")
                    continue
                payload = _strip_id(lbl)
                payload.setdefault("color", payload.get("color", "berry-red"))
                created = client.create_label(board, name=payload.get("name"), color=payload.get("color"))
                label_map[old_id] = created["id"]
                typer.echo(f"  Created label: {created['name']} [{created['id']}]")

            # Create groups
            group_map: Dict[str, str] = {}
            for grp in data.get("customFieldGroups", []):
                if grp.get("name") in existing_groups:
                    group_map[grp.get("id")] = existing_groups[grp.get("name")]["id"]
                    typer.echo(f"Custom field group exists, skipping: {grp['name']}")
                    continue
                try:
                    # Send minimal payload — Planka rejects export-only keys like createdAt/updatedAt/baseCustomFieldGroupId
                    payload = {"name": grp.get("name"), "position": grp.get("position", 65536.0)}
                    typer.echo(f"    Creating group payload: {payload}")
                    created = client._post(f"/api/boards/{board}/custom-field-groups", json=payload)["item"]
                    group_map[grp.get("id")] = created["id"]
                    typer.echo(f"  Created custom field group: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create group {grp.get('name')}: {e} -- payload: {payload}")

            # Create fields
            field_map: Dict[str, str] = {}  # old field id -> new field id
            for fld in data.get("customFields", []):
                if fld.get("name") in existing_fields:
                    field_map[fld.get("id")] = existing_fields[fld.get("name")]["id"]
                    typer.echo(f"Custom field exists, skipping: {fld['name']}")
                    continue
                old_gid = fld.get("customFieldGroupId") or fld.get("groupId")
                new_gid = group_map.get(old_gid) if old_gid else None
                if not new_gid:
                    typer.echo(f"  Skipping custom field {fld.get('name')}: no matching group found")
                    continue
                payload = {"name": fld.get("name"), "position": fld.get("position", 65536.0)}
                if fld.get("showOnFrontOfCard") is not None:
                    payload["showOnFrontOfCard"] = bool(fld.get("showOnFrontOfCard"))
                try:
                    created = client._post(f"/api/custom-field-groups/{new_gid}/custom-fields", json=payload)["item"]
                    field_map[fld.get("id")] = created["id"]
                    typer.echo(f"  Created custom field: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create custom field {fld.get('name')}: {e}")

            # Create lists
            list_map: Dict[str, str] = {}
            for lst in data.get("lists", []):
                lst_name = lst.get("name")
                if lst_name in existing_lists:
                    existing = existing_lists[lst_name]
                    list_map[lst.get("id")] = existing["id"]
                    typer.echo(f"List exists, skipping: {lst_name}")
                    continue
                # Skip unnamed/system lists
                if not lst_name:
                    typer.echo(f"  Skipping unnamed/system list with id {lst.get('id')}")
                    continue
                payload = _strip_id(lst)
                try:
                    # Include type and color if present — API may require 'type'
                    create_payload = {"name": payload.get("name", ""), "position": payload.get("position", 65536.0)}
                    if payload.get("type"):
                        create_payload["type"] = payload.get("type")
                    if payload.get("color"):
                        create_payload["color"] = payload.get("color")
                    typer.echo(f"    Creating list payload: {create_payload}")
                    created = client._post(f"/api/boards/{board}/lists", json=create_payload)["item"]
                    list_map[lst.get("id")] = created["id"]
                    typer.echo(f"  Created list: {created['name']} [{created['id']}]")
                except Exception as e:
                    typer.echo(f"  Failed to create list {lst.get('name')}: {e} -- payload: {payload}")

            # Refresh included (to include newly created lists)
            included = client.get_board_included(board).get("included", {})
            # Cards: only create if name not present in target list
            cards_existing = included.get("cards", [])
            cards_by_list_name = {}
            for c in cards_existing:
                cards_by_list_name.setdefault(c.get("listId"), set()).add(c.get("name"))

            # Build card->label mapping if present in export
            card_label_map: Dict[str, list] = {}
            for key in ("cardLabels", "card_label", "cardsLabels", "cardLabelRelations", "cards_label"):
                for rel in data.get(key, []):
                    if rel.get("cardId") and rel.get("labelId"):
                        card_label_map.setdefault(rel["cardId"], []).append(rel["labelId"])

            me = client.get_me()
            my_id = me.get("id") if me else None

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
                try:
                    create_payload = {"name": payload.get("name", ""), "position": payload.get("position", 65536.0), "description": payload.get("description")}
                    typer.echo(f"    Creating card payload: {create_payload} in list {target_list_id}")
                    created = client.create_card(target_list_id, name=create_payload["name"], position=create_payload["position"], description=create_payload.get("description"))
                    typer.echo(f"  Created card: {created['name']} [{created['id']}] in list {target_list_id}")

                    old_card_id = c.get("id")
                    embedded_label_ids = c.get("labelIds") or []
                    relation_label_ids = card_label_map.get(old_card_id, [])
                    old_label_ids = embedded_label_ids if embedded_label_ids else relation_label_ids
                    for old_label_id in old_label_ids:
                        new_label_id = label_map.get(old_label_id)
                        if new_label_id:
                            try:
                                client.add_label_to_card(created["id"], new_label_id)
                                typer.echo(f"    Attached label {new_label_id} to card {created['id']}")
                            except Exception as e:
                                typer.echo(f"    Failed to attach label {new_label_id} to card {created['id']}: {e}")

                    if my_id:
                        try:
                            client.remove_member_from_card(created["id"], my_id)
                            typer.echo(f"    Removed auto-assigned member {my_id} from card {created['id']}")
                        except Exception:
                            pass

                    # Set custom field values
                    for fv in c.get("customFieldValues", []):
                        old_gid = fv.get("customFieldGroupId")
                        old_fid = fv.get("customFieldId")
                        new_gid = group_map.get(old_gid)
                        new_fid = field_map.get(old_fid)
                        if new_gid and new_fid and fv.get("content"):
                            try:
                                client.set_custom_field_value(created["id"], new_gid, new_fid, fv["content"])
                                typer.echo(f"    Set custom field value [{fv['content']}] on card {created['id']}")
                            except Exception as e:
                                typer.echo(f"    Failed to set custom field value on card {created['id']}: {e}")

                except Exception as e:
                    typer.echo(f"  Failed to create card {c.get('name')}: {e} -- payload: {create_payload}")

    except PlankaError as e:
        typer.echo(f"API error: {e}", err=True)
        raise typer.Exit(1)


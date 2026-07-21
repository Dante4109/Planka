"""
list_points.py — "List Point Totals" automation.

Keeps list titles in sync with the sum of a custom "Points" field
across all non-closed cards in that list.

Title format:  "List Name (25)"
               "List Name"        ← when total is 0 or no cards have points

Usage (one-shot):
    from planka_tools.api.client import PlankaClient
    from planka_tools.automations.list_points import sync_list_point_totals

    with PlankaClient() as client:
        changes = sync_list_point_totals(client, board_id="...")
        for change in changes:
            print(change)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from planka_tools.api.client import PlankaClient

# Matches a trailing " (N)" or " (N.N)" suffix on a list name.
_POINTS_SUFFIX = re.compile(r"\s*\(\d+(?:\.\d+)?\)$")


def strip_points_suffix(name: str) -> str:
    """Remove a trailing point-total suffix (e.g. "In-Progress (23)" -> "In-Progress")."""
    return _POINTS_SUFFIX.sub("", name).strip()


@dataclass
class ListUpdate:
    list_id: str
    old_name: str
    new_name: str
    total: float


def sync_list_point_totals(
    client: PlankaClient,
    board_id: str,
    points_field_name: str = "Points",
) -> list[ListUpdate]:
    """
    Compute per-list point totals and update list titles that are out of sync.

    Returns a list of ListUpdate records for every list that was changed.
    """
    resp = client._get(f"/api/boards/{board_id}")
    included = resp.get("included", {})

    # Locate the Points custom field definition
    custom_fields = included.get("customFields", [])
    points_field = next(
        (f for f in custom_fields if f["name"] == points_field_name), None
    )
    if not points_field:
        return []  # field doesn't exist on this board — nothing to do

    points_field_id = points_field["id"]

    # Map each card to its list (skip closed/archived cards)
    card_to_list: dict[str, str] = {
        c["id"]: c["listId"]
        for c in included.get("cards", [])
        if not c.get("isClosed")
    }

    # Sum points per list
    list_totals: dict[str, float] = {}
    for val in included.get("customFieldValues", []):
        if val["customFieldId"] != points_field_id:
            continue
        card_id = val["cardId"]
        list_id = card_to_list.get(card_id)
        if list_id is None:
            continue  # card is closed or not on board
        try:
            points = float(val["content"])
        except (ValueError, TypeError):
            continue
        list_totals[list_id] = list_totals.get(list_id, 0.0) + points

    # Update list names where the total has changed
    changes: list[ListUpdate] = []
    for lst in included.get("lists", []):
        list_id = lst["id"]
        current_name: str = lst.get("name") or ""
        base_name = _POINTS_SUFFIX.sub("", current_name).strip()

        total = list_totals.get(list_id, 0.0)
        if total > 0:
            display = str(int(total)) if total == int(total) else str(round(total, 2))
            new_name = f"{base_name} ({display})"
        else:
            new_name = base_name

        if new_name != current_name:
            client.update_list(list_id, name=new_name)
            changes.append(ListUpdate(list_id, current_name, new_name, total))

    return changes

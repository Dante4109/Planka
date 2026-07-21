"""
list_lookup.py — Find a board list by its "base" name, ignoring any trailing
point-total suffix that the sync_list_point_totals automation may have
appended (e.g. "In-Progress (23)" still matches a lookup for "In-Progress").

`PlankaClient.find_list()` does an exact-name match, which fails on boards
where the point-totals automation is active — job scripts should use this
helper instead whenever they resolve a list by name.
"""

from __future__ import annotations

from typing import Optional

from planka_tools.api.client import PlankaClient
from planka_tools.automations.list_points import strip_points_suffix


def find_list_by_base_name(client: PlankaClient, board_id: str, name: str) -> Optional[dict]:
    """Return the first list on board_id whose name matches `name`, ignoring a point-total suffix."""
    return next(
        (
            l for l in client.get_lists(board_id)
            if l.get("name") and strip_points_suffix(l["name"]) == name
        ),
        None,
    )

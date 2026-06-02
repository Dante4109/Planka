"""
handlers.py — Planka webhook event routing.

Receives parsed event payloads and calls the appropriate automation.

Planka event payload shape:
    {
        "event": "<eventName>",
        "data": {
            "item": {...},
            "included": {...}
        },
        "prevData": {...} | None,
        "user": {...} | None
    }
"""

from __future__ import annotations

import logging
from typing import Any

from planka_tools.api.client import PlankaClient
from planka_tools.automations.list_points import sync_list_point_totals

log = logging.getLogger(__name__)


def _board_id_from_custom_field_event(payload: dict[str, Any]) -> str | None:
    """Extract board ID from a customFieldValue* event."""
    try:
        return payload["data"]["included"]["boards"][0]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def _board_id_from_card_event(payload: dict[str, Any]) -> str | None:
    """Extract board ID from a card* event."""
    try:
        return payload["data"]["item"]["boardId"]
    except (KeyError, TypeError):
        return None


def _is_card_list_move(payload: dict[str, Any]) -> bool:
    """Return True if a cardUpdate moved the card to a different list."""
    try:
        old_list = payload["prevData"]["item"]["listId"]
        new_list = payload["data"]["item"]["listId"]
        return old_list != new_list
    except (KeyError, TypeError):
        return False


def handle_event(event: str, payload: dict[str, Any], client: PlankaClient) -> None:
    """
    Route an incoming webhook event and trigger the appropriate automation.

    Relevant events:
        customFieldValueUpdate  — Points field set or changed
        customFieldValueDelete  — Points field cleared
        cardUpdate              — Card moved between lists (detect via prevData)
        cardDelete              — Card removed (recompute source list totals)
    """
    board_id: str | None = None

    if event in ("customFieldValueUpdate", "customFieldValueDelete"):
        board_id = _board_id_from_custom_field_event(payload)

    elif event == "cardUpdate":
        if _is_card_list_move(payload):
            board_id = _board_id_from_card_event(payload)
        else:
            log.debug("cardUpdate ignored — not a list move")

    elif event == "cardDelete":
        board_id = _board_id_from_card_event(payload)

    else:
        log.debug("Unhandled event type: %s", event)
        return

    if not board_id:
        log.warning("Could not extract board ID from event '%s' — skipping", event)
        return

    log.info("Triggered by '%s' on board %s — syncing list point totals", event, board_id)
    try:
        changes = sync_list_point_totals(client, board_id)
        for c in changes:
            log.info("  %s → %s (%.0f pts)", c.old_name, c.new_name, c.total)
        if not changes:
            log.debug("No list names needed updating.")
    except Exception as exc:
        log.error("sync_list_point_totals failed for board %s: %s", board_id, exc)

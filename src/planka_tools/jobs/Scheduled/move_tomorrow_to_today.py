"""Move all cards from 'Tomorrow' to 'Today' on Daily Workflow, daily at 8:00 AM."""

from __future__ import annotations

import logging

from planka_tools.api.client import PlankaClient
from planka_tools.jobs.list_lookup import find_list_by_base_name

log = logging.getLogger(__name__)

TRIGGER = {"type": "cron", "hour": 8, "minute": 0}


def run(client: PlankaClient) -> None:
    project = client.find_project("Trello Import")
    if not project:
        log.warning("Project 'Trello Import' not found — skipping")
        return
    board = client.find_board(project["id"], "Daily Workflow")
    if not board:
        log.warning("Board 'Daily Workflow' not found — skipping")
        return
    src_list = find_list_by_base_name(client, board["id"], "Tomorrow")
    dst_list = find_list_by_base_name(client, board["id"], "Today")
    if not src_list or not dst_list:
        log.warning("List 'Tomorrow' or 'Today' not found on board — skipping")
        return
    cards = [c for c in client.get_cards(board["id"]) if c.get("listId") == src_list["id"]]
    for card in cards:
        client.move_card(card["id"], dst_list["id"])
    log.info("Moved %d card(s) from Tomorrow to Today", len(cards))

"""Move all cards from 'This Month' to 'This Week' on Daily Workflow, monthly on the 1st at 4:00 AM."""

from __future__ import annotations

import logging

from planka_tools.api.client import PlankaClient

log = logging.getLogger(__name__)

TRIGGER = {"type": "cron", "day": 1, "hour": 4, "minute": 0}


def run(client: PlankaClient) -> None:
    project = client.find_project("Trello Import")
    if not project:
        log.warning("Project 'Trello Import' not found — skipping")
        return
    board = client.find_board(project["id"], "Daily Workflow")
    if not board:
        log.warning("Board 'Daily Workflow' not found — skipping")
        return
    src_list = client.find_list(board["id"], "This Month")
    dst_list = client.find_list(board["id"], "This Week")
    if not src_list or not dst_list:
        log.warning("List 'This Month' or 'This Week' not found on board — skipping")
        return
    cards = [c for c in client.get_cards(board["id"]) if c.get("listId") == src_list["id"]]
    for card in cards:
        client.move_card(card["id"], dst_list["id"])
    log.info("Moved %d card(s) from This Month to This Week", len(cards))

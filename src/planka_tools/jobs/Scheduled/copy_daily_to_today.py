"""Copy each card in 'Daily' (Personal board) to 'Today' (Daily Workflow board), daily at 6:00 AM."""

from __future__ import annotations

import logging

from planka_tools.api.client import PlankaClient

log = logging.getLogger(__name__)

TRIGGER = {"type": "cron", "hour": 6, "minute": 0}


def run(client: PlankaClient) -> None:
    project = client.find_project("Trello Import")
    if not project:
        log.warning("Project 'Trello Import' not found — skipping")
        return
    src_board = client.find_board(project["id"], "Personal")
    dst_board = client.find_board(project["id"], "Daily Workflow")
    if not src_board or not dst_board:
        log.warning("Source or destination board not found — skipping")
        return
    src_list = client.find_list(src_board["id"], "Daily")
    dst_list = client.find_list(dst_board["id"], "Today")
    if not src_list or not dst_list:
        log.warning("List 'Daily' or 'Today' not found — skipping")
        return
    cards = [c for c in client.get_cards(src_board["id"]) if c.get("listId") == src_list["id"]]
    for card in cards:
        copy = client.duplicate_card(card["id"])
        client.move_card(copy["id"], dst_list["id"])
    log.info("Copied %d card(s) from Daily to Today", len(cards))

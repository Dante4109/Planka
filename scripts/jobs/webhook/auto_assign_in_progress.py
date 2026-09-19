"""
Manually trigger auto_assign_in_progress for a real card, without waiting
for an actual webhook event.

Requires the CARD_ID env var (pass with `docker exec -e CARD_ID=<id> ...`).
Resolves the card's real board and the board's "In-Progress" list, then
simulates a cardUpdate payload that moves the card into that list.
"""
import logging
import os
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from planka_tools.api.client import PlankaClient
from planka_tools.jobs.list_lookup import find_list_by_base_name
from planka_tools.jobs.Webhook import auto_assign_in_progress as job

card_id = os.environ["CARD_ID"]

with PlankaClient() as client:
    card = client.get_card(card_id)
    board_id = card["boardId"]
    in_progress = find_list_by_base_name(client, board_id, "In-Progress")
    if not in_progress:
        raise SystemExit("No 'In-Progress' list found on this card's board")

    payload = {
        "prevData": {"item": {"listId": card["listId"]}},
        "data": {"item": {"id": card_id, "listId": in_progress["id"], "boardId": board_id}},
    }
    job.run("cardUpdate", payload, client)

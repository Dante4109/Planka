"""Unit tests for the auto_assign_in_progress Webhook example job."""
from __future__ import annotations

from unittest.mock import MagicMock

from planka_tools.jobs.Webhook import auto_assign_in_progress


def _client():
    mc = MagicMock()
    mc.find_project.return_value = {"id": "p1"}
    mc.find_board.return_value = {"id": "b1"}
    mc.find_list.return_value = {"id": "l-inprog"}
    return mc


def _payload(old_list_id: str, new_list_id: str, board_id: str = "b1", card_id: str = "c1"):
    return {
        "prevData": {"item": {"listId": old_list_id}},
        "data": {"item": {"id": card_id, "listId": new_list_id, "boardId": board_id}},
    }


class TestAutoAssignInProgress:
    def test_assigns_user_when_moved_to_in_progress(self, monkeypatch):
        monkeypatch.setenv("AUTO_ASSIGN_USER_ID", "user-1")
        mc = _client()
        auto_assign_in_progress.run("cardUpdate", _payload("l-other", "l-inprog"), mc)
        mc.add_member_to_card.assert_called_once_with("c1", "user-1")

    def test_no_call_when_moved_to_different_list(self, monkeypatch):
        monkeypatch.setenv("AUTO_ASSIGN_USER_ID", "user-1")
        mc = _client()
        auto_assign_in_progress.run("cardUpdate", _payload("l-other", "l-something-else"), mc)
        mc.add_member_to_card.assert_not_called()

    def test_no_call_when_prev_data_missing(self, monkeypatch):
        monkeypatch.setenv("AUTO_ASSIGN_USER_ID", "user-1")
        mc = _client()
        auto_assign_in_progress.run("cardUpdate", {"data": {"item": {}}}, mc)
        mc.add_member_to_card.assert_not_called()

    def test_no_call_when_board_lookup_fails(self, monkeypatch):
        monkeypatch.setenv("AUTO_ASSIGN_USER_ID", "user-1")
        mc = _client()
        mc.find_board.return_value = None
        auto_assign_in_progress.run("cardUpdate", _payload("l-other", "l-inprog"), mc)
        mc.add_member_to_card.assert_not_called()

    def test_no_call_when_list_lookup_fails(self, monkeypatch):
        monkeypatch.setenv("AUTO_ASSIGN_USER_ID", "user-1")
        mc = _client()
        mc.find_list.return_value = None
        auto_assign_in_progress.run("cardUpdate", _payload("l-other", "l-inprog"), mc)
        mc.add_member_to_card.assert_not_called()

    def test_no_call_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("AUTO_ASSIGN_USER_ID", raising=False)
        mc = _client()
        auto_assign_in_progress.run("cardUpdate", _payload("l-other", "l-inprog"), mc)
        mc.add_member_to_card.assert_not_called()

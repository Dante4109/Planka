"""Unit tests for the four Scheduled example jobs, using a mocked PlankaClient."""
from __future__ import annotations

from unittest.mock import MagicMock

from planka_tools.jobs.Scheduled import (
    copy_daily_to_today,
    move_this_month_to_this_week,
    move_tomorrow_to_today,
    sweep_past_due,
)


def _lists_by_board(mapping: dict[str, list[dict]]):
    """Return a side_effect function for get_lists(board_id), keyed by board_id."""
    return lambda board_id: mapping.get(board_id, [])


class TestMoveTomorrowToToday:
    def _client(self):
        mc = MagicMock()
        mc.find_project.return_value = {"id": "p1"}
        mc.find_board.return_value = {"id": "b1"}
        # Names carry a point-total suffix, like sync_list_point_totals appends —
        # base-name matching must still resolve these.
        mc.get_lists.return_value = [
            {"id": "l-tom", "name": "Tomorrow (6)"},
            {"id": "l-tod", "name": "Today (1)"},
        ]
        return mc

    def test_moves_matching_cards(self):
        mc = self._client()
        mc.get_cards.return_value = [
            {"id": "c1", "listId": "l-tom"},
            {"id": "c2", "listId": "other"},
        ]
        move_tomorrow_to_today.run(mc)
        mc.find_project.assert_called_once_with("Trello Import")
        mc.find_board.assert_called_once_with("p1", "Daily Workflow")
        mc.move_card.assert_called_once_with("c1", "l-tod")

    def test_missing_project_returns_early(self):
        mc = MagicMock()
        mc.find_project.return_value = None
        move_tomorrow_to_today.run(mc)
        mc.get_cards.assert_not_called()
        mc.move_card.assert_not_called()

    def test_missing_board_returns_early(self):
        mc = MagicMock()
        mc.find_project.return_value = {"id": "p1"}
        mc.find_board.return_value = None
        move_tomorrow_to_today.run(mc)
        mc.get_cards.assert_not_called()

    def test_missing_list_returns_early(self):
        mc = self._client()
        mc.get_lists.return_value = []
        move_tomorrow_to_today.run(mc)
        mc.get_cards.assert_not_called()


class TestMoveThisMonthToThisWeek:
    def test_moves_matching_cards(self):
        mc = MagicMock()
        mc.find_project.return_value = {"id": "p1"}
        mc.find_board.return_value = {"id": "b1"}
        mc.get_lists.return_value = [
            {"id": "l-m", "name": "This Month (8)"},
            {"id": "l-w", "name": "This Week (13)"},
        ]
        mc.get_cards.return_value = [
            {"id": "c1", "listId": "l-m"},
            {"id": "c2", "listId": "other"},
        ]
        move_this_month_to_this_week.run(mc)
        mc.move_card.assert_called_once_with("c1", "l-w")

    def test_missing_project_returns_early(self):
        mc = MagicMock()
        mc.find_project.return_value = None
        move_this_month_to_this_week.run(mc)
        mc.move_card.assert_not_called()


class TestSweepPastDue:
    def _client(self):
        mc = MagicMock()
        mc.find_project.return_value = {"id": "p1"}
        mc.find_board.return_value = {"id": "b1"}
        mc.get_lists.return_value = [{"id": "l-pd", "name": "Past-Due"}]
        return mc

    def test_moves_only_past_due_not_already_in_list(self):
        mc = self._client()
        mc.get_cards.return_value = [
            {"id": "c1", "listId": "l-x", "dueDate": "2020-01-01T00:00:00.000Z"},
            {"id": "c2", "listId": "l-x", "dueDate": "2099-01-01T00:00:00.000Z"},
            {"id": "c3", "listId": "l-pd", "dueDate": "2020-01-01T00:00:00.000Z"},
            {"id": "c4", "listId": "l-x"},
        ]
        sweep_past_due.run(mc)
        mc.move_card.assert_called_once_with("c1", "l-pd")

    def test_missing_list_returns_early(self):
        mc = MagicMock()
        mc.find_project.return_value = {"id": "p1"}
        mc.find_board.return_value = {"id": "b1"}
        mc.get_lists.return_value = []
        sweep_past_due.run(mc)
        mc.get_cards.assert_not_called()

    def test_missing_board_returns_early(self):
        mc = MagicMock()
        mc.find_project.return_value = {"id": "p1"}
        mc.find_board.return_value = None
        sweep_past_due.run(mc)
        mc.get_cards.assert_not_called()


class TestCopyDailyToToday:
    def _client(self):
        mc = MagicMock()
        mc.find_project.return_value = {"id": "p1"}
        mc.find_board.side_effect = lambda pid, name: {
            "Personal": {"id": "b-src"}, "Daily Workflow": {"id": "b-dst"},
        }[name]
        mc.get_lists.side_effect = _lists_by_board({
            "b-src": [{"id": "l-daily", "name": "Daily"}],
            "b-dst": [{"id": "l-today", "name": "Today (1)"}],
        })
        return mc

    def test_copies_and_moves_matching_cards(self):
        mc = self._client()
        mc.get_cards.return_value = [
            {"id": "c1", "listId": "l-daily"},
            {"id": "c2", "listId": "other"},
        ]
        mc.duplicate_card.return_value = {"id": "copy-1"}
        copy_daily_to_today.run(mc)
        mc.duplicate_card.assert_called_once_with("c1")
        mc.move_card.assert_called_once_with("copy-1", "l-today")

    def test_missing_source_board_returns_early(self):
        mc = MagicMock()
        mc.find_project.return_value = {"id": "p1"}
        mc.find_board.return_value = None
        copy_daily_to_today.run(mc)
        mc.duplicate_card.assert_not_called()

    def test_missing_list_returns_early(self):
        mc = self._client()
        mc.get_lists.side_effect = None
        mc.get_lists.return_value = []
        copy_daily_to_today.run(mc)
        mc.get_cards.assert_not_called()

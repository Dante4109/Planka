"""Unit tests for the card list command (card/commands.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from planka_tools.card.commands import app
from planka_tools.api.client import PlankaError

runner = CliRunner()

LIST_ID = "list-1"
BOARD_ID = "board-1"
LIST_A_ID = "list-a"
LIST_B_ID = "list-b"


def _patch_client(mock_client):
    """Patch PlankaClient in card.commands to use mock_client as the context manager result."""
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_cls.return_value.__exit__.return_value = False
    return patch("planka_tools.card.commands.PlankaClient", mock_cls)


class TestCardListByList:
    def test_lists_cards_in_list(self):
        mc = MagicMock()
        mc.get_list.return_value = {"id": LIST_ID, "name": "Backlog", "boardId": BOARD_ID}
        mc.get_cards.return_value = [
            {"id": "card-1", "name": "First card", "listId": LIST_ID, "position": 1},
            {"id": "card-2", "name": "Second card", "listId": LIST_ID, "position": 2},
            {"id": "card-x", "name": "Other list card", "listId": "list-other", "position": 1},
        ]
        with _patch_client(mc):
            result = runner.invoke(app, ["list", "--list", LIST_ID])
        assert result.exit_code == 0, result.output
        assert f"Backlog [{LIST_ID}]" in result.output
        assert "Card" in result.output and "Id" in result.output and "Name" in result.output
        assert "card-1" in result.output
        assert "First card" in result.output
        assert "card-2" in result.output
        assert "Second card" in result.output
        assert "card-x" not in result.output
        mc.get_list.assert_called_once_with(LIST_ID)
        mc.get_cards.assert_called_once_with(BOARD_ID)

    def test_cards_ordered_by_position(self):
        mc = MagicMock()
        mc.get_list.return_value = {"id": LIST_ID, "name": "Backlog", "boardId": BOARD_ID}
        mc.get_cards.return_value = [
            {"id": "card-2", "name": "Second", "listId": LIST_ID, "position": 2},
            {"id": "card-1", "name": "First", "listId": LIST_ID, "position": 1},
        ]
        with _patch_client(mc):
            result = runner.invoke(app, ["list", "--list", LIST_ID])
        assert result.output.index("First") < result.output.index("Second")

    def test_none_position_does_not_crash(self):
        """Real Planka data can have position: None on system/archive lists and cards."""
        mc = MagicMock()
        mc.get_list.return_value = {"id": LIST_ID, "name": "Backlog", "boardId": BOARD_ID}
        mc.get_cards.return_value = [
            {"id": "card-1", "name": "No position", "listId": LIST_ID, "position": None},
            {"id": "card-2", "name": "Has position", "listId": LIST_ID, "position": 1},
        ]
        with _patch_client(mc):
            result = runner.invoke(app, ["list", "--list", LIST_ID])
        assert result.exit_code == 0, result.output
        assert "No position" in result.output
        assert "Has position" in result.output

    def test_empty_list_shows_no_cards_message(self):
        mc = MagicMock()
        mc.get_list.return_value = {"id": LIST_ID, "name": "Empty List", "boardId": BOARD_ID}
        mc.get_cards.return_value = []
        with _patch_client(mc):
            result = runner.invoke(app, ["list", "--list", LIST_ID])
        assert result.exit_code == 0
        assert "(no cards)" in result.output


class TestCardListByBoard:
    def test_lists_one_table_per_list(self):
        mc = MagicMock()
        mc.get_lists.return_value = [
            {"id": LIST_A_ID, "name": "To Do", "position": 1},
            {"id": LIST_B_ID, "name": "Done", "position": 2},
        ]
        mc.get_cards.return_value = [
            {"id": "card-1", "name": "Task one", "listId": LIST_A_ID, "position": 1},
            {"id": "card-2", "name": "Task two", "listId": LIST_B_ID, "position": 1},
        ]
        with _patch_client(mc):
            result = runner.invoke(app, ["list", "--board", BOARD_ID])
        assert result.exit_code == 0, result.output
        assert f"To Do [{LIST_A_ID}]" in result.output
        assert f"Done [{LIST_B_ID}]" in result.output
        assert result.output.index("To Do") < result.output.index("Done")
        assert "Task one" in result.output
        assert "Task two" in result.output
        mc.get_lists.assert_called_once_with(BOARD_ID)
        mc.get_cards.assert_called_once_with(BOARD_ID)

    def test_list_with_no_cards_shows_empty_table(self):
        mc = MagicMock()
        mc.get_lists.return_value = [{"id": LIST_A_ID, "name": "Empty", "position": 1}]
        mc.get_cards.return_value = []
        with _patch_client(mc):
            result = runner.invoke(app, ["list", "--board", BOARD_ID])
        assert "Empty" in result.output
        assert "(no cards)" in result.output

    def test_none_position_lists_and_cards_do_not_crash(self):
        """Real Planka data can have position: None on system/archive lists and cards."""
        mc = MagicMock()
        mc.get_lists.return_value = [
            {"id": LIST_A_ID, "name": "Archive", "position": None},
            {"id": LIST_B_ID, "name": "To Do", "position": 1},
        ]
        mc.get_cards.return_value = [
            {"id": "card-1", "name": "Archived card", "listId": LIST_A_ID, "position": None},
            {"id": "card-2", "name": "Active card", "listId": LIST_B_ID, "position": 1},
        ]
        with _patch_client(mc):
            result = runner.invoke(app, ["list", "--board", BOARD_ID])
        assert result.exit_code == 0, result.output
        assert "Archived card" in result.output
        assert "Active card" in result.output


class TestCardListValidation:
    def test_no_options_errors(self):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1
        assert "provide either" in result.output

    def test_both_options_errors(self):
        result = runner.invoke(app, ["list", "--list", LIST_ID, "--board", BOARD_ID])
        assert result.exit_code == 1
        assert "only one of" in result.output


class TestCardListErrors:
    def test_api_error_exits_1(self):
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.side_effect = PlankaError(404, "E_NOT_FOUND", "List not found")
        with patch("planka_tools.card.commands.PlankaClient", mock_cls):
            result = runner.invoke(app, ["list", "--list", LIST_ID])
        assert result.exit_code == 1
        assert "API error" in result.output

    def test_unexpected_error_exits_1(self):
        mc = MagicMock()
        mc.get_list.side_effect = RuntimeError("boom")
        with _patch_client(mc):
            result = runner.invoke(app, ["list", "--list", LIST_ID])
        assert result.exit_code == 1
        assert "Unexpected error" in result.output

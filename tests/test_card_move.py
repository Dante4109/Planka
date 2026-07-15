"""Unit tests for the card move command (card/commands.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from planka_tools.card.commands import app
from planka_tools.api.client import PlankaError

runner = CliRunner()

CARD_ID = "card-1"
LIST_ID = "list-2"
BOARD_ID = "board-2"


def _patch_client(mock_client):
    """Patch PlankaClient in card.commands to use mock_client as the context manager result."""
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_cls.return_value.__exit__.return_value = False
    return patch("planka_tools.card.commands.PlankaClient", mock_cls)


class TestCardMoveSuccess:
    def test_moves_card_to_list(self):
        mc = MagicMock()
        mc.move_card.return_value = {"id": CARD_ID, "listId": LIST_ID, "boardId": BOARD_ID}
        with _patch_client(mc):
            result = runner.invoke(app, ["--card", CARD_ID, "--list", LIST_ID])
        assert result.exit_code == 0, result.output
        mc.move_card.assert_called_once_with(CARD_ID, LIST_ID)

    def test_reports_success_message(self):
        mc = MagicMock()
        mc.move_card.return_value = {"id": CARD_ID, "listId": LIST_ID, "boardId": BOARD_ID}
        with _patch_client(mc):
            result = runner.invoke(app, ["--card", CARD_ID, "--list", LIST_ID])
        assert CARD_ID in result.output
        assert LIST_ID in result.output

    def test_short_options(self):
        mc = MagicMock()
        mc.move_card.return_value = {"id": CARD_ID, "listId": LIST_ID}
        with _patch_client(mc):
            result = runner.invoke(app, ["-c", CARD_ID, "-l", LIST_ID])
        assert result.exit_code == 0, result.output
        mc.move_card.assert_called_once_with(CARD_ID, LIST_ID)


class TestCardMoveErrors:
    def test_missing_card_option_errors(self):
        result = runner.invoke(app, ["--list", LIST_ID])
        assert result.exit_code != 0

    def test_missing_list_option_errors(self):
        result = runner.invoke(app, ["--card", CARD_ID])
        assert result.exit_code != 0

    def test_api_error_exits_1(self):
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.side_effect = PlankaError(404, "E_NOT_FOUND", "Card not found")
        with patch("planka_tools.card.commands.PlankaClient", mock_cls):
            result = runner.invoke(app, ["--card", CARD_ID, "--list", LIST_ID])
        assert result.exit_code == 1
        assert "API error" in result.output

    def test_unexpected_error_exits_1(self):
        mc = MagicMock()
        mc.move_card.side_effect = RuntimeError("boom")
        with _patch_client(mc):
            result = runner.invoke(app, ["--card", CARD_ID, "--list", LIST_ID])
        assert result.exit_code == 1
        assert "Unexpected error" in result.output

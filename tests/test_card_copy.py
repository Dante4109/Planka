"""Unit tests for the card copy command (card/commands.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from planka_tools.card.commands import app
from planka_tools.api.client import PlankaError

runner = CliRunner()

CARD_ID = "card-1"
NEW_CARD_ID = "card-2"
LIST_ID = "list-1"
OTHER_LIST_ID = "list-2"


def _patch_client(mock_client):
    """Patch PlankaClient in card.commands to use mock_client as the context manager result."""
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_cls.return_value.__exit__.return_value = False
    return patch("planka_tools.card.commands.PlankaClient", mock_cls)


class TestCardCopySuccess:
    def test_copies_card_in_place(self):
        mc = MagicMock()
        mc.duplicate_card.return_value = {"id": NEW_CARD_ID, "listId": LIST_ID}
        with _patch_client(mc):
            result = runner.invoke(app, ["copy", "--card", CARD_ID])
        assert result.exit_code == 0, result.output
        mc.duplicate_card.assert_called_once_with(CARD_ID)
        mc.move_card.assert_not_called()
        assert NEW_CARD_ID in result.output
        assert LIST_ID in result.output

    def test_copies_card_to_different_list(self):
        mc = MagicMock()
        mc.duplicate_card.return_value = {"id": NEW_CARD_ID, "listId": LIST_ID}
        mc.move_card.return_value = {"id": NEW_CARD_ID, "listId": OTHER_LIST_ID}
        with _patch_client(mc):
            result = runner.invoke(app, ["copy", "--card", CARD_ID, "--list", OTHER_LIST_ID])
        assert result.exit_code == 0, result.output
        mc.duplicate_card.assert_called_once_with(CARD_ID)
        mc.move_card.assert_called_once_with(NEW_CARD_ID, OTHER_LIST_ID)
        assert NEW_CARD_ID in result.output
        assert OTHER_LIST_ID in result.output

    def test_short_options(self):
        mc = MagicMock()
        mc.duplicate_card.return_value = {"id": NEW_CARD_ID, "listId": LIST_ID}
        mc.move_card.return_value = {"id": NEW_CARD_ID, "listId": OTHER_LIST_ID}
        with _patch_client(mc):
            result = runner.invoke(app, ["copy", "-c", CARD_ID, "-l", OTHER_LIST_ID])
        assert result.exit_code == 0, result.output
        mc.move_card.assert_called_once_with(NEW_CARD_ID, OTHER_LIST_ID)


class TestCardCopyErrors:
    def test_missing_card_option_errors(self):
        result = runner.invoke(app, ["copy"])
        assert result.exit_code != 0

    def test_api_error_exits_1(self):
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.side_effect = PlankaError(404, "E_NOT_FOUND", "Card not found")
        with patch("planka_tools.card.commands.PlankaClient", mock_cls):
            result = runner.invoke(app, ["copy", "--card", CARD_ID])
        assert result.exit_code == 1
        assert "API error" in result.output

    def test_unexpected_error_exits_1(self):
        mc = MagicMock()
        mc.duplicate_card.side_effect = RuntimeError("boom")
        with _patch_client(mc):
            result = runner.invoke(app, ["copy", "--card", CARD_ID])
        assert result.exit_code == 1
        assert "Unexpected error" in result.output

    def test_move_error_after_duplicate_exits_1(self):
        mc = MagicMock()
        mc.duplicate_card.return_value = {"id": NEW_CARD_ID, "listId": LIST_ID}
        mc.move_card.side_effect = PlankaError(404, "E_NOT_FOUND", "List not found")
        with _patch_client(mc):
            result = runner.invoke(app, ["copy", "--card", CARD_ID, "--list", OTHER_LIST_ID])
        assert result.exit_code == 1
        assert "API error" in result.output

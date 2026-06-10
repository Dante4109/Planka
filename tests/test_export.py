"""Unit tests for export command (export/commands.py)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from planka_tools.export.commands import app
from planka_tools.api.client import PlankaError

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOARD_ID = "board-123"
LABEL_ID = "lbl-1"
LIST_ID = "list-1"
CARD_ID = "card-1"
FIELD_GROUP_ID = "grp-1"
FIELD_ID = "fld-1"

MINIMAL_INCLUDED = {
    "lists": [{"id": LIST_ID, "name": "Backlog", "position": 65536, "type": "active"}],
    "labels": [{"id": LABEL_ID, "name": "Bug", "color": "red"}],
    "customFieldGroups": [{"id": FIELD_GROUP_ID, "name": "Details"}],
    "customFields": [{"id": FIELD_ID, "name": "Priority", "customFieldGroupId": FIELD_GROUP_ID}],
    "customFieldValues": [
        {
            "id": "cfv-1",
            "cardId": CARD_ID,
            "customFieldGroupId": FIELD_GROUP_ID,
            "customFieldId": FIELD_ID,
            "content": "High",
        }
    ],
    "cards": [{"id": CARD_ID, "name": "Fix it", "listId": LIST_ID, "position": 65536}],
    "cardLabels": [{"id": "cl-1", "cardId": CARD_ID, "labelId": LABEL_ID}],
}

BOARD_RESPONSE = {
    "item": {"id": BOARD_ID, "name": "Test Board"},
    "included": MINIMAL_INCLUDED,
}


def _make_mock_client(board_response=None):
    """Return a mock PlankaClient instance with get_board_included configured."""
    mock_client = MagicMock()
    mock_client.get_board_included.return_value = board_response or BOARD_RESPONSE
    return mock_client


def _patch_client(mock_client):
    """Context-manager patch for the export commands module's PlankaClient."""
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_cls.return_value.__exit__.return_value = False
    return patch("planka_tools.export.commands.PlankaClient", mock_cls)


# ---------------------------------------------------------------------------
# Structure-only export (no --cards)
# ---------------------------------------------------------------------------

class TestExportStructureOnly:
    def test_writes_output_file(self, tmp_path):
        out = tmp_path / "out.json"
        mock_client = _make_mock_client()
        with _patch_client(mock_client):
            result = runner.invoke(app, ["--board", BOARD_ID, "--output", str(out)])
        assert result.exit_code == 0, result.output
        assert out.exists()

    def test_output_contains_board_and_lists(self, tmp_path):
        out = tmp_path / "out.json"
        mock_client = _make_mock_client()
        with _patch_client(mock_client):
            runner.invoke(app, ["--board", BOARD_ID, "--output", str(out)])
        data = json.loads(out.read_text())
        assert data["board"]["id"] == BOARD_ID
        assert len(data["lists"]) == 1

    def test_output_contains_labels_and_custom_fields(self, tmp_path):
        out = tmp_path / "out.json"
        mock_client = _make_mock_client()
        with _patch_client(mock_client):
            runner.invoke(app, ["--board", BOARD_ID, "--output", str(out)])
        data = json.loads(out.read_text())
        assert len(data["labels"]) == 1
        assert data["labels"][0]["name"] == "Bug"
        assert len(data["customFieldGroups"]) == 1
        assert len(data["customFields"]) == 1

    def test_output_has_no_cards_key(self, tmp_path):
        out = tmp_path / "out.json"
        mock_client = _make_mock_client()
        with _patch_client(mock_client):
            runner.invoke(app, ["--board", BOARD_ID, "--output", str(out)])
        data = json.loads(out.read_text())
        assert "cards" not in data

    def test_default_output_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_client = _make_mock_client()
        with _patch_client(mock_client):
            result = runner.invoke(app, ["--board", BOARD_ID])
        assert result.exit_code == 0
        expected = tmp_path / f"board_{BOARD_ID}_export.json"
        assert expected.exists()


# ---------------------------------------------------------------------------
# Export with --cards
# ---------------------------------------------------------------------------

class TestExportWithCards:
    def _run(self, tmp_path, board_response=None):
        out = tmp_path / "out.json"
        mock_client = _make_mock_client(board_response)
        with _patch_client(mock_client):
            result = runner.invoke(app, ["--board", BOARD_ID, "--cards", "--output", str(out)])
        return result, json.loads(out.read_text()) if out.exists() else {}

    def test_cards_key_present(self, tmp_path):
        result, data = self._run(tmp_path)
        assert result.exit_code == 0
        assert "cards" in data
        assert len(data["cards"]) == 1

    def test_card_has_embedded_label_ids(self, tmp_path):
        _, data = self._run(tmp_path)
        card = data["cards"][0]
        assert card["labelIds"] == [LABEL_ID]

    def test_card_has_embedded_label_names(self, tmp_path):
        _, data = self._run(tmp_path)
        card = data["cards"][0]
        assert card["labelNames"] == ["Bug"]

    def test_card_has_embedded_custom_field_values(self, tmp_path):
        _, data = self._run(tmp_path)
        card = data["cards"][0]
        assert len(card["customFieldValues"]) == 1
        fv = card["customFieldValues"][0]
        assert fv["content"] == "High"
        assert fv["customFieldGroupId"] == FIELD_GROUP_ID
        assert fv["customFieldId"] == FIELD_ID

    def test_card_with_no_labels(self, tmp_path):
        """A card not in cardLabels gets empty labelIds/labelNames."""
        import copy
        resp = copy.deepcopy(BOARD_RESPONSE)
        resp["included"]["cards"] = [{"id": "card-no-lbl", "name": "Clean Card", "listId": LIST_ID}]
        resp["included"]["cardLabels"] = []
        _, data = self._run(tmp_path, resp)
        card = data["cards"][0]
        assert card["labelIds"] == []
        assert card["labelNames"] == []

    def test_card_with_unknown_label_id_silently_skipped(self, tmp_path):
        """Labels not found in the label_by_id lookup are omitted from labelNames."""
        import copy
        resp = copy.deepcopy(BOARD_RESPONSE)
        resp["included"]["cardLabels"] = [{"cardId": CARD_ID, "labelId": "phantom-lbl"}]
        _, data = self._run(tmp_path, resp)
        card = data["cards"][0]
        # labelIds includes the id but labelNames skips the unknown one
        assert "phantom-lbl" in card["labelIds"]
        assert card["labelNames"] == []

    def test_card_label_relations_included_in_export(self, tmp_path):
        _, data = self._run(tmp_path)
        assert "cardLabels" in data
        assert len(data["cardLabels"]) == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestExportErrors:
    def test_api_error_exits_with_code_1(self, tmp_path):
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.side_effect = PlankaError(404, "E_NOT_FOUND", "Board missing")
        with patch("planka_tools.export.commands.PlankaClient", mock_cls):
            result = runner.invoke(app, ["--board", "bad-id", "--output", str(tmp_path / "o.json")])
        assert result.exit_code == 1

    def test_connection_error_exits_with_code_1(self, tmp_path):
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.side_effect = ConnectionError("refused")
        with patch("planka_tools.export.commands.PlankaClient", mock_cls):
            result = runner.invoke(app, ["--board", "bad-id", "--output", str(tmp_path / "o.json")])
        assert result.exit_code == 1

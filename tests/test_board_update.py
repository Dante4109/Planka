"""Unit tests for update_board command (board/commands.py)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from planka_tools.board.commands import app
from planka_tools.api.client import PlankaError
from tests.conftest import (
    BOARD_SRC_ID, LABEL_OLD_ID, LABEL_NEW_ID,
    GROUP_OLD_ID, GROUP_NEW_ID, FIELD_OLD_ID, FIELD_NEW_ID,
    LIST_OLD_ID, LIST_NEW_ID, CARD_OLD_ID, CARD_NEW_ID,
    SAMPLE_EXPORT,
)

runner = CliRunner()
TARGET_BOARD = "target-board-1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _included_empty():
    return {
        "lists": [],
        "labels": [],
        "customFieldGroups": [],
        "customFields": [],
        "customFieldValues": [],
        "cards": [],
        "cardLabels": [],
    }


def _included_with_list():
    """Included payload AFTER list creation (second get_board_included call)."""
    return {
        "lists": [{"id": LIST_NEW_ID, "name": "Backlog"}],
        "labels": [{"id": LABEL_NEW_ID, "name": "Bug"}],
        "customFieldGroups": [{"id": GROUP_NEW_ID, "name": "Details"}],
        "customFields": [{"id": FIELD_NEW_ID, "name": "Priority"}],
        "customFieldValues": [],
        "cards": [],
        "cardLabels": [],
    }


def _post_side_effect(path: str, json: dict = None) -> dict:
    if "custom-field-groups" in path and "custom-fields" not in path:
        return {"item": {"id": GROUP_NEW_ID, "name": json.get("name", "Group")}}
    if "custom-fields" in path:
        return {"item": {"id": FIELD_NEW_ID, "name": json.get("name", "Field")}}
    if "/lists" in path:
        return {"item": {"id": LIST_NEW_ID, "name": json.get("name", "List")}}
    return {"item": {"id": "generic-id"}}


def _build_mock_client(first_included=None, second_included=None):
    """
    Build a mock client where get_board_included returns two different values:
    - first call: the board as it is before the import (e.g. no lists)
    - second call: the board after lists are created (refresh step)
    """
    mc = MagicMock()

    first = {"included": first_included or _included_empty()}
    second = {"included": second_included or _included_with_list()}
    mc.get_board_included.side_effect = [first, second]

    mc.create_label.return_value = {"id": LABEL_NEW_ID, "name": "Bug", "color": "red"}
    mc._post.side_effect = _post_side_effect
    mc.create_card.return_value = {"id": CARD_NEW_ID, "name": "Fix the bug"}
    mc.get_me.return_value = {"id": "me-user-1"}
    mc.add_label_to_card.return_value = {"id": "cl-new-1"}
    mc.remove_member_from_card.return_value = {}
    mc.set_custom_field_value.return_value = {"id": "cfv-new-1", "content": "High"}
    return mc


def _patch_client(mock_client):
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_cls.return_value.__exit__.return_value = False
    return patch("planka_tools.board.commands.PlankaClient", mock_cls)


# ---------------------------------------------------------------------------
# Tests: idempotency / skip-existing
# ---------------------------------------------------------------------------

class TestUpdateBoardSkipsExisting:
    def test_skips_existing_label(self, export_file):
        first_inc = {**_included_empty(), "labels": [{"id": LABEL_NEW_ID, "name": "Bug"}]}
        mc = _build_mock_client(first_included=first_inc)
        with _patch_client(mc):
            result = runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        assert result.exit_code == 0
        mc.create_label.assert_not_called()
        assert "Label exists" in result.output

    def test_skips_existing_custom_field_group(self, export_file):
        first_inc = {**_included_empty(), "customFieldGroups": [{"id": GROUP_NEW_ID, "name": "Details"}]}
        mc = _build_mock_client(first_included=first_inc)
        with _patch_client(mc):
            result = runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        group_calls = [c for c in mc._post.call_args_list if "custom-field-groups" in c.args[0] and "custom-fields" not in c.args[0]]
        assert len(group_calls) == 0
        assert "Custom field group exists" in result.output

    def test_skips_existing_custom_field(self, export_file):
        first_inc = {
            **_included_empty(),
            "customFieldGroups": [{"id": GROUP_NEW_ID, "name": "Details"}],
            "customFields": [{"id": FIELD_NEW_ID, "name": "Priority"}],
        }
        mc = _build_mock_client(first_included=first_inc)
        with _patch_client(mc):
            result = runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        field_calls = [c for c in mc._post.call_args_list if "custom-fields" in c.args[0]]
        assert len(field_calls) == 0
        assert "Custom field exists" in result.output

    def test_skips_existing_list(self, export_file):
        first_inc = {**_included_empty(), "lists": [{"id": LIST_NEW_ID, "name": "Backlog"}]}
        # Second call also returns the list so cards can be resolved
        second_inc = {**_included_with_list(), "lists": [{"id": LIST_NEW_ID, "name": "Backlog"}]}
        mc = _build_mock_client(first_included=first_inc, second_included=second_inc)
        with _patch_client(mc):
            result = runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        list_calls = [c for c in mc._post.call_args_list if "/lists" in c.args[0]]
        assert len(list_calls) == 0
        assert "List exists" in result.output

    def test_skips_existing_card_by_name_in_list(self, export_file):
        """If a card with the same name already exists in the target list, skip it."""
        first_inc = _included_empty()
        # After list creation, the target list already has the card
        second_inc = {
            **_included_with_list(),
            "cards": [{"id": "pre-existing-card", "name": "Fix the bug", "listId": LIST_NEW_ID}],
        }
        mc = _build_mock_client(first_included=first_inc, second_included=second_inc)
        with _patch_client(mc):
            result = runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        mc.create_card.assert_not_called()
        assert "Card exists in list, skipping" in result.output


# ---------------------------------------------------------------------------
# Tests: create missing items
# ---------------------------------------------------------------------------

class TestUpdateBoardCreatesMissing:
    def test_creates_label_when_missing(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        mc.create_label.assert_called_once_with(TARGET_BOARD, name="Bug", color="red")

    def test_creates_custom_field_group_with_minimal_payload(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        group_calls = [c for c in mc._post.call_args_list if "custom-field-groups" in c.args[0] and "custom-fields" not in c.args[0]]
        assert len(group_calls) == 1
        payload = group_calls[0].kwargs.get("json") or group_calls[0].args[1]
        assert "createdAt" not in payload
        assert "boardId" not in payload
        assert payload["name"] == "Details"

    def test_creates_custom_field_with_show_on_front(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        field_calls = [c for c in mc._post.call_args_list if "custom-fields" in c.args[0]]
        assert len(field_calls) == 1
        payload = field_calls[0].kwargs.get("json") or field_calls[0].args[1]
        assert payload.get("showOnFrontOfCard") is True

    def test_creates_list_with_type_field(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        list_calls = [c for c in mc._post.call_args_list if "/lists" in c.args[0]]
        assert len(list_calls) == 1
        payload = list_calls[0].kwargs.get("json") or list_calls[0].args[1]
        assert payload["name"] == "Backlog"
        assert payload.get("type") == "active"

    def test_creates_card_in_mapped_list(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        mc.create_card.assert_called_once()
        args = mc.create_card.call_args.args
        assert args[0] == LIST_NEW_ID


# ---------------------------------------------------------------------------
# Tests: card enrichment (labels + field values)
# ---------------------------------------------------------------------------

class TestUpdateBoardCardEnrichment:
    def test_attaches_label_to_new_card(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        mc.add_label_to_card.assert_called_once_with(CARD_NEW_ID, LABEL_NEW_ID)

    def test_removes_auto_assigned_member_from_new_card(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        mc.remove_member_from_card.assert_called_once_with(CARD_NEW_ID, "me-user-1")

    def test_sets_custom_field_value_on_new_card(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        mc.set_custom_field_value.assert_called_once_with(
            CARD_NEW_ID, GROUP_NEW_ID, FIELD_NEW_ID, "High"
        )

    def test_existing_field_id_in_field_map_for_custom_values(self, export_file):
        """When a field already exists, its ID must be tracked in field_map so values can still be set."""
        first_inc = {
            **_included_empty(),
            "customFieldGroups": [{"id": GROUP_NEW_ID, "name": "Details"}],
            "customFields": [{"id": FIELD_NEW_ID, "name": "Priority"}],
        }
        mc = _build_mock_client(first_included=first_inc)
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        mc.set_custom_field_value.assert_called_once_with(
            CARD_NEW_ID, GROUP_NEW_ID, FIELD_NEW_ID, "High"
        )


# ---------------------------------------------------------------------------
# Tests: miscellaneous / edge cases
# ---------------------------------------------------------------------------

class TestUpdateBoardEdgeCases:
    def test_skips_unnamed_list(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            result = runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        assert "Skipping unnamed" in result.output

    def test_skips_card_with_unmapped_list(self, export_file):
        """Card whose source listId has no mapping is skipped with an explanatory message."""
        mc = _build_mock_client()
        with _patch_client(mc):
            result = runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        # The orphan card ("Orphan Card" with listId "list-does-not-exist") must be skipped
        assert "Skipping card (list missing)" in result.output

    def test_get_board_included_called_twice(self, export_file):
        """update_board should call get_board_included twice: before + after list creation."""
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(export_file)])
        assert mc.get_board_included.call_count == 2

    def test_api_error_exits_with_code_1(self, tmp_path):
        f = tmp_path / "e.json"
        f.write_text(json.dumps(SAMPLE_EXPORT))
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.side_effect = PlankaError(401, "E_UNAUTHORIZED", "Auth failed")
        with patch("planka_tools.board.commands.PlankaClient", mock_cls):
            result = runner.invoke(app, ["update", "--board", TARGET_BOARD, "--import", str(f)])
        assert result.exit_code == 1

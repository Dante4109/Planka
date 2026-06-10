"""Unit tests for create_board command (board/commands.py)."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, call, patch

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
TARGET_PROJECT = "proj-1"
TARGET_BOARD_NEW = "new-board-1"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_mock_client():
    """
    Return a MagicMock PlankaClient with sensible default returns for all
    methods called by create_board.
    """
    mc = MagicMock()
    mc.create_board.return_value = {"id": TARGET_BOARD_NEW, "name": "Sample Board"}
    mc.get_labels.return_value = []  # no pre-existing labels
    mc.create_label.return_value = {"id": LABEL_NEW_ID, "name": "Bug", "color": "red"}
    mc.get_me.return_value = {"id": "me-user-1"}

    # _post is used for groups, fields, lists
    mc._post.side_effect = _post_side_effect

    mc.create_card.return_value = {"id": CARD_NEW_ID, "name": "Fix the bug"}
    mc.add_label_to_card.return_value = {"id": "cl-new-1"}
    mc.remove_member_from_card.return_value = {}
    mc.set_custom_field_value.return_value = {"id": "cfv-new-1", "content": "High"}
    return mc


def _post_side_effect(path: str, json: dict = None) -> dict:
    """Route _post calls to realistic responses based on URL path."""
    if "custom-field-groups" in path and "custom-fields" not in path:
        return {"item": {"id": GROUP_NEW_ID, "name": json.get("name", "Group")}}
    if "custom-fields" in path:
        return {"item": {"id": FIELD_NEW_ID, "name": json.get("name", "Field")}}
    if "/lists" in path:
        return {"item": {"id": LIST_NEW_ID, "name": json.get("name", "List")}}
    return {"item": {"id": "generic-id"}}


def _patch_client(mock_client):
    """Patch PlankaClient in board.commands to use mock_client as the context manager result."""
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_cls.return_value.__exit__.return_value = False
    return patch("planka_tools.board.commands.PlankaClient", mock_cls)


# ---------------------------------------------------------------------------
# Tests: board creation
# ---------------------------------------------------------------------------

class TestCreateBoardBasic:
    def test_creates_board_with_name_from_export(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            result = runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        assert result.exit_code == 0, result.output
        mc.create_board.assert_called_once_with(TARGET_PROJECT, name="Sample Board")

    def test_exit_code_0_on_success(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            result = runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        assert result.exit_code == 0

    def test_reports_new_board_id_in_output(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            result = runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        assert TARGET_BOARD_NEW in result.output


# ---------------------------------------------------------------------------
# Tests: labels
# ---------------------------------------------------------------------------

class TestCreateBoardLabels:
    def test_creates_missing_label(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        mc.create_label.assert_called_once_with(TARGET_BOARD_NEW, name="Bug", color="red")

    def test_skips_existing_label(self, export_file):
        mc = _build_mock_client()
        mc.get_labels.return_value = [{"id": LABEL_NEW_ID, "name": "Bug", "color": "red"}]
        with _patch_client(mc):
            result = runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        mc.create_label.assert_not_called()
        assert "Label exists" in result.output

    def test_label_map_built_for_existing_label(self, export_file):
        """If a label already exists, its ID should still be mapped (for card attachment)."""
        mc = _build_mock_client()
        mc.get_labels.return_value = [{"id": LABEL_NEW_ID, "name": "Bug", "color": "red"}]
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        # add_label_to_card should still be called on the card using the existing label ID
        mc.add_label_to_card.assert_called_once_with(CARD_NEW_ID, LABEL_NEW_ID)


# ---------------------------------------------------------------------------
# Tests: custom field groups
# ---------------------------------------------------------------------------

class TestCreateBoardCustomFieldGroups:
    def test_creates_custom_field_group_with_minimal_payload(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        # Find the group creation call
        group_calls = [
            c for c in mc._post.call_args_list
            if "custom-field-groups" in c.args[0] and "custom-fields" not in c.args[0]
        ]
        assert len(group_calls) == 1
        payload = group_calls[0].kwargs.get("json") or group_calls[0].args[1]
        # Must NOT include stale export-only keys
        assert "createdAt" not in payload
        assert "updatedAt" not in payload
        assert "boardId" not in payload
        assert "baseCustomFieldGroupId" not in payload
        # Must include name and position
        assert payload["name"] == "Details"
        assert "position" in payload

    def test_creates_custom_field_in_new_group(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        field_calls = [
            c for c in mc._post.call_args_list
            if "custom-fields" in c.args[0]
        ]
        assert len(field_calls) == 1
        url = field_calls[0].args[0]
        assert GROUP_NEW_ID in url

    def test_field_creation_includes_show_on_front(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        field_calls = [
            c for c in mc._post.call_args_list
            if "custom-fields" in c.args[0]
        ]
        payload = field_calls[0].kwargs.get("json") or field_calls[0].args[1]
        assert payload.get("showOnFrontOfCard") is True


# ---------------------------------------------------------------------------
# Tests: lists
# ---------------------------------------------------------------------------

class TestCreateBoardLists:
    def test_creates_named_list_with_type(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        list_calls = [c for c in mc._post.call_args_list if "/lists" in c.args[0]]
        assert len(list_calls) == 1  # unnamed list is skipped
        payload = list_calls[0].kwargs.get("json") or list_calls[0].args[1]
        assert payload["name"] == "Backlog"
        assert payload.get("type") == "active"

    def test_skips_unnamed_list(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            result = runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        assert "Skipping unnamed" in result.output


# ---------------------------------------------------------------------------
# Tests: cards
# ---------------------------------------------------------------------------

class TestCreateBoardCards:
    def test_creates_card_in_correct_list(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        mc.create_card.assert_called_once()
        call_kwargs = mc.create_card.call_args
        assert call_kwargs.args[0] == LIST_NEW_ID or call_kwargs.kwargs.get("list_id") == LIST_NEW_ID

    def test_skips_card_with_missing_list(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            result = runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        assert "Skipping card (list missing)" in result.output

    def test_attaches_label_to_card(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        mc.add_label_to_card.assert_called_once_with(CARD_NEW_ID, LABEL_NEW_ID)

    def test_removes_auto_assigned_member(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        mc.remove_member_from_card.assert_called_once_with(CARD_NEW_ID, "me-user-1")

    def test_sets_custom_field_value_on_card(self, export_file):
        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(export_file)])
        mc.set_custom_field_value.assert_called_once_with(
            CARD_NEW_ID, GROUP_NEW_ID, FIELD_NEW_ID, "High"
        )

    def test_no_custom_field_value_set_if_content_empty(self, tmp_path):
        """Cards with empty custom field content should not call set_custom_field_value."""
        import copy
        export = copy.deepcopy(SAMPLE_EXPORT)
        export["cards"][0]["customFieldValues"][0]["content"] = ""
        f = tmp_path / "export.json"
        f.write_text(json.dumps(export))

        mc = _build_mock_client()
        with _patch_client(mc):
            runner.invoke(app, ["create", "--project", TARGET_PROJECT, "--import", str(f)])
        mc.set_custom_field_value.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestCreateBoardErrors:
    def test_api_error_exits_1(self, tmp_path):
        f = tmp_path / "e.json"
        f.write_text(json.dumps(SAMPLE_EXPORT))
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.side_effect = PlankaError(401, "E_UNAUTHORIZED", "Auth failed")
        with patch("planka_tools.board.commands.PlankaClient", mock_cls):
            result = runner.invoke(app, ["create", "--project", "p", "--import", str(f)])
        assert result.exit_code == 1

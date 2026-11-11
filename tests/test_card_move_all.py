"""Unit tests for the card move-all command (card/commands.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from planka_tools.api.client import PlankaError
from planka_tools.card.commands import app

runner = CliRunner()


def _patch_client(mock_client):
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_cls.return_value.__exit__.return_value = False
    return patch("planka_tools.card.commands.PlankaClient", mock_cls)


LISTS = {
    "src": {"id": "src", "boardId": "b1", "name": "Today"},
    "done": {"id": "done", "boardId": "b1", "name": "Done (5)"},
    "b2done": {"id": "b2done", "boardId": "b2", "name": "Done"},
    "b3done": {"id": "b3done", "boardId": "b3", "name": "Done"},
    "b2todo": {"id": "b2todo", "boardId": "b2", "name": "To-Do"},
}
BOARDS = {
    "p1": [{"id": "b1", "name": "Daily"}, {"id": "b2", "name": "Archive"}],
    "p2": [{"id": "b3", "name": "Daily"}],
}
CARDS = {
    "b1": [
        {"id": "c2", "listId": "src", "position": 200},
        {"id": "c1", "listId": "src", "position": 100},
        {"id": "x", "listId": "other", "position": 1},
        {"id": "d1", "listId": "done", "position": 1000},
    ],
    "b2": [],
    "b3": [],
}


def _client():
    mc = MagicMock()

    def get_list(i):
        if i not in LISTS:
            raise PlankaError(404, "E_NOT_FOUND", "List not found")
        return LISTS[i]

    mc.get_list.side_effect = get_list
    mc.get_lists.side_effect = lambda b: [l for l in LISTS.values() if l["boardId"] == b]
    mc.get_cards.side_effect = lambda b: CARDS[b]
    mc.get_projects.return_value = [{"id": "p1", "name": "Trello Import"}, {"id": "p2", "name": "Other"}]
    mc.get_project_boards.side_effect = lambda p: BOARDS[p]
    return mc


def _run(*args):
    mc = _client()
    with _patch_client(mc):
        result = runner.invoke(app, ["move-all", *args])
    return mc, result


def _moves(mc):
    return [(c.args[0], c.args[1]) for c in mc.move_card.call_args_list]


P = ("--project", "Trello Import")


def test_ids_in_order_after_existing():
    mc, result = _run("--list", "src", "--list", "done")
    assert result.exit_code == 0, result.output
    assert _moves(mc) == [("c1", "done"), ("c2", "done")]
    positions = [c.kwargs["position"] for c in mc.move_card.call_args_list]
    assert positions == sorted(positions) and positions[0] > 1000


def test_destination_list_is_required():
    mc, result = _run("--list", "src")
    assert result.exit_code == 1
    assert "second --list is required" in result.output
    mc.move_card.assert_not_called()


def test_source_list_by_name_with_board_and_project():
    mc, result = _run(*P, "--board", "Daily", "--list", "today", "--list", "Done")
    assert result.exit_code == 0, result.output
    assert _moves(mc) == [("c1", "done"), ("c2", "done")]


def test_source_list_by_name_with_board_id():
    mc, result = _run("--board", "b1", "--list", "Today", "--list", "Done")
    assert result.exit_code == 0, result.output


def test_full_control_example_everything_specified_twice():
    mc, result = _run(
        "--project", "Trello Import", "--board", "Daily", "--list", "Today",
        "--project", "Trello Import", "--board", "Daily", "--list", "done",
    )
    assert result.exit_code == 0, result.output
    assert _moves(mc) == [("c1", "done"), ("c2", "done")]


def test_second_list_only_inherits_source_board():
    mc, result = _run(*P, "--board", "Daily", "--list", "Today", "--list", "Done")
    assert result.exit_code == 0, result.output
    assert _moves(mc)[0][1] == "done"


def test_destination_on_other_board_inherits_project():
    mc, result = _run(*P, "--board", "Daily", "--list", "Today", "--board", "Archive", "--list", "To-Do")
    assert result.exit_code == 0, result.output
    assert _moves(mc) == [("c1", "b2todo"), ("c2", "b2todo")]


def test_other_board_by_id_with_done_list():
    mc, result = _run(*P, "--board", "Daily", "--list", "Today", "--board", "b2", "--list", "Done")
    assert result.exit_code == 0, result.output
    assert _moves(mc)[0][1] == "b2done"


def test_destination_in_other_project_by_board_name():
    mc, result = _run(
        *P, "--board", "Daily", "--list", "Today",
        "--project", "Other", "--board", "Daily", "--list", "Done",
    )
    assert result.exit_code == 0, result.output
    assert _moves(mc)[0][1] == "b3done"


def test_destination_project_alone_reuses_source_board_name():
    mc, result = _run(*P, "--board", "Daily", "--list", "Today", "--list", "Done", "--project", "Other")
    assert result.exit_code == 0, result.output
    assert _moves(mc)[0][1] == "b3done"


def test_destination_project_alone_without_board_errors():
    mc, result = _run("--project", "Trello Import", "--list", "src", "--list", "Done", "--project", "Other")
    assert result.exit_code == 1
    assert "needs a --board" in result.output
    mc.move_card.assert_not_called()


def test_destination_list_id_from_other_board_is_rejected():
    mc, result = _run("--list", "src", "--list", "b2todo")
    assert result.exit_code == 1
    assert "valid list name or list-id" in result.output
    mc.move_card.assert_not_called()


def test_destination_list_id_on_other_board_when_board_given():
    mc, result = _run("--list", "src", "--board", "b1", "--board", "b2", "--list", "b2todo")
    assert result.exit_code == 0, result.output
    assert _moves(mc)[0][1] == "b2todo"


def test_missing_list_errors():
    mc, result = _run("--board", "b1")
    assert result.exit_code == 1
    assert "--list is required" in result.output


def test_more_than_two_values_errors():
    mc, result = _run("--list", "a", "--list", "b", "--list", "c")
    assert result.exit_code == 1
    assert "at most twice" in result.output


def test_board_name_in_multiple_projects_is_ambiguous():
    mc, result = _run("--list", "Today", "--list", "Done", "--board", "Daily")
    assert result.exit_code == 1
    assert "ambiguous" in result.output and "--project" in result.output
    mc.move_card.assert_not_called()


def test_unknown_project_errors():
    mc, result = _run("--project", "Nope", "--list", "Today", "--list", "Done", "--board", "Daily")
    assert result.exit_code == 1
    assert "valid project name or project-id" in result.output


def test_project_name_given_as_board_gets_hint():
    mc, result = _run("--list", "Today", "--list", "Done", "--board", "Other")
    assert result.exit_code == 1
    assert "is a project name" in result.output


def test_unknown_source_name_errors_and_asks_for_valid_name():
    mc, result = _run(*P, "--list", "Nope", "--list", "Done", "--board", "Daily")
    assert result.exit_code == 1
    assert "not found" in result.output and "valid list name or list-id" in result.output
    mc.move_card.assert_not_called()


def test_source_name_without_board_errors():
    mc, result = _run("--list", "Today", "--list", "Done")
    assert result.exit_code == 1
    assert "valid list-id" in result.output
    mc.move_card.assert_not_called()


def test_unknown_destination_list_errors():
    mc, result = _run("--list", "src", "--list", "Nowhere", "--board", "b1")
    assert result.exit_code == 1
    assert "valid list name or list-id" in result.output
    mc.move_card.assert_not_called()


def test_unknown_destination_board_errors():
    mc, result = _run("--list", "src", "--list", "Done", "--board", "b1", "--board", "Missing")
    assert result.exit_code == 1
    assert "valid board name or board-id" in result.output


def test_missing_done_list_errors():
    mc = _client()
    mc.get_lists.side_effect = lambda b: [LISTS["src"]]
    with _patch_client(mc):
        result = runner.invoke(app, ["move-all", "--list", "src", "--list", "Done"])
    assert result.exit_code == 1
    assert "Done" in result.output and "valid list name or list-id" in result.output
    mc.move_card.assert_not_called()


def test_same_source_and_destination_errors():
    mc, result = _run("--list", "src", "--board", "b1", "--list", "Today")
    assert result.exit_code == 1
    mc.move_card.assert_not_called()


def test_empty_list_is_noop():
    mc = _client()
    with _patch_client(mc), patch.dict(CARDS, {"b1": []}):
        result = runner.invoke(app, ["move-all", "--list", "src", "--list", "done"])
    assert result.exit_code == 0
    mc.move_card.assert_not_called()


def test_card_name_filter_moves_only_named_card():
    mc = _client()
    CARDS["b1"][1]["name"] = "Write report"
    CARDS["b1"][0]["name"] = "Other"
    with _patch_client(mc):
        result = runner.invoke(app, ["move-all", "-l", "src", "-l", "done", "-c", "write REPORT"])
    assert result.exit_code == 0, result.output
    assert _moves(mc) == [("c1", "done")]


def test_card_name_not_found_moves_nothing():
    mc, result = _run("-l", "src", "-l", "done", "-c", "nope")
    assert result.exit_code == 1
    assert "not found in source list" in result.output
    mc.move_card.assert_not_called()

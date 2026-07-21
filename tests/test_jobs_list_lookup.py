"""Unit tests for jobs/list_lookup.py — base-name list resolution."""
from __future__ import annotations

from unittest.mock import MagicMock

from planka_tools.jobs.list_lookup import find_list_by_base_name


def test_matches_name_with_points_suffix():
    mc = MagicMock()
    mc.get_lists.return_value = [{"id": "l1", "name": "In-Progress (23)"}]
    result = find_list_by_base_name(mc, "b1", "In-Progress")
    assert result == {"id": "l1", "name": "In-Progress (23)"}


def test_matches_name_without_suffix():
    mc = MagicMock()
    mc.get_lists.return_value = [{"id": "l1", "name": "Past-Due"}]
    result = find_list_by_base_name(mc, "b1", "Past-Due")
    assert result == {"id": "l1", "name": "Past-Due"}


def test_ignores_lists_with_none_name():
    mc = MagicMock()
    mc.get_lists.return_value = [
        {"id": "l1", "name": None},
        {"id": "l2", "name": "Today (1)"},
    ]
    result = find_list_by_base_name(mc, "b1", "Today")
    assert result == {"id": "l2", "name": "Today (1)"}


def test_returns_none_when_no_match():
    mc = MagicMock()
    mc.get_lists.return_value = [{"id": "l1", "name": "Something Else"}]
    assert find_list_by_base_name(mc, "b1", "Today") is None

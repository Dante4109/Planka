"""Unit tests for discovered-job dispatch in webhook/handlers.py (handle_event)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from planka_tools.webhook import handlers


def _job_module(name: str, events: list[str], run=None):
    module = MagicMock()
    module.__name__ = name
    module.EVENTS = events
    if run is not None:
        module.run = run
    return module


class TestDiscoveredJobDispatch:
    def test_dispatches_to_matching_job(self):
        job = _job_module("demo", ["cardCreate"])
        with patch("planka_tools.webhook.handlers.loader.load_webhook_jobs", return_value=[job]):
            client = MagicMock()
            handlers.handle_event("cardCreate", {"data": {"item": {}}}, client)
        job.run.assert_called_once_with("cardCreate", {"data": {"item": {}}}, client)

    def test_skips_job_when_event_does_not_match(self):
        job = _job_module("demo", ["cardDelete"])
        with patch("planka_tools.webhook.handlers.loader.load_webhook_jobs", return_value=[job]):
            client = MagicMock()
            handlers.handle_event("cardCreate", {"data": {"item": {}}}, client)
        job.run.assert_not_called()

    def test_failing_job_does_not_block_second_job(self):
        def boom(event, payload, client):
            raise RuntimeError("boom")

        failing = _job_module("failing", ["cardCreate"], run=boom)
        ok = _job_module("ok", ["cardCreate"])
        with patch(
            "planka_tools.webhook.handlers.loader.load_webhook_jobs",
            return_value=[failing, ok],
        ):
            client = MagicMock()
            handlers.handle_event("cardCreate", {"data": {"item": {}}}, client)
        ok.run.assert_called_once()

    def test_legacy_sync_list_point_totals_unaffected_by_discovered_jobs(self):
        job = _job_module("unrelated", ["cardCreate"])
        payload = {
            "prevData": {"item": {"listId": "l-old"}},
            "data": {"item": {"listId": "l-new", "boardId": "b1"}},
        }
        with patch("planka_tools.webhook.handlers.loader.load_webhook_jobs", return_value=[job]), \
             patch("planka_tools.webhook.handlers.sync_list_point_totals") as mock_sync:
            mock_sync.return_value = []
            client = MagicMock()
            handlers.handle_event("cardUpdate", payload, client)
        mock_sync.assert_called_once_with(client, "b1")
        job.run.assert_not_called()  # job only subscribes to cardCreate

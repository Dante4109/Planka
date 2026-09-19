"""Unit tests for the job auto-discovery loader (jobs/loader.py)."""
from __future__ import annotations

import logging

from planka_tools.jobs import loader


class TestLoadScheduledJobs:
    def test_valid_job_loaded(self, tmp_path):
        (tmp_path / "good.py").write_text(
            "TRIGGER = {'type': 'cron', 'hour': 8}\ndef run(client): pass\n"
        )
        modules = loader.load_scheduled_jobs(tmp_path)
        assert len(modules) == 1
        assert modules[0].__name__ == "good"

    def test_missing_trigger_skipped(self, tmp_path, caplog):
        (tmp_path / "bad.py").write_text("def run(client): pass\n")
        with caplog.at_level(logging.ERROR):
            modules = loader.load_scheduled_jobs(tmp_path)
        assert modules == []
        assert "bad.py" in caplog.text
        assert "TRIGGER" in caplog.text

    def test_missing_run_skipped(self, tmp_path, caplog):
        (tmp_path / "bad.py").write_text("TRIGGER = {'type': 'cron', 'hour': 8}\n")
        with caplog.at_level(logging.ERROR):
            modules = loader.load_scheduled_jobs(tmp_path)
        assert modules == []
        assert "run" in caplog.text

    def test_import_error_skipped(self, tmp_path, caplog):
        (tmp_path / "bad.py").write_text("raise ImportError('boom')\n")
        with caplog.at_level(logging.ERROR):
            modules = loader.load_scheduled_jobs(tmp_path)
        assert modules == []
        assert "boom" in caplog.text

    def test_empty_directory_returns_empty_list(self, tmp_path):
        assert loader.load_scheduled_jobs(tmp_path) == []

    def test_nonexistent_directory_returns_empty_list(self, tmp_path):
        assert loader.load_scheduled_jobs(tmp_path / "does-not-exist") == []

    def test_init_file_ignored(self, tmp_path):
        (tmp_path / "__init__.py").write_text("")
        assert loader.load_scheduled_jobs(tmp_path) == []


class TestLoadWebhookJobs:
    def test_valid_job_loaded(self, tmp_path):
        (tmp_path / "good.py").write_text(
            "EVENTS = ['cardUpdate']\ndef run(event, payload, client): pass\n"
        )
        modules = loader.load_webhook_jobs(tmp_path)
        assert len(modules) == 1
        assert modules[0].__name__ == "good"

    def test_missing_events_skipped(self, tmp_path, caplog):
        (tmp_path / "bad.py").write_text("def run(event, payload, client): pass\n")
        with caplog.at_level(logging.ERROR):
            modules = loader.load_webhook_jobs(tmp_path)
        assert modules == []
        assert "EVENTS" in caplog.text

    def test_missing_run_skipped(self, tmp_path, caplog):
        (tmp_path / "bad.py").write_text("EVENTS = ['cardUpdate']\n")
        with caplog.at_level(logging.ERROR):
            modules = loader.load_webhook_jobs(tmp_path)
        assert modules == []
        assert "run" in caplog.text

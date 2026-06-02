"""
server.py — Flask webhook receiver for Planka events.

Listens for POST /webhook from Planka, validates the optional bearer token,
and routes to the appropriate handler.

Environment variables (read from .env):
    PLANKA_INTERNAL_URL   — Planka API base URL from inside Docker (http://planka:1337)
    PLANKA_WEBHOOK_TOKEN  — Expected bearer token in Authorization header (optional)
    PLANKA_WEBHOOK_PORT   — Port to bind on (default: 5001)
    PLANKA_API_KEY        — API key used by the client to authenticate to Planka
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

from planka_tools.api.client import PlankaClient, PlankaError
from planka_tools.webhook.handlers import handle_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("planka.webhook")

app = Flask(__name__)

_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


def _env(key: str, default: str | None = None) -> str | None:
    val = os.environ.get(key)
    if val:
        return val
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1]
    return default


_WEBHOOK_TOKEN: str | None = None


def _get_token() -> str | None:
    global _WEBHOOK_TOKEN
    if _WEBHOOK_TOKEN is None:
        _WEBHOOK_TOKEN = _env("PLANKA_WEBHOOK_TOKEN")
    return _WEBHOOK_TOKEN


@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive a Planka webhook event."""
    # Token validation (optional but recommended)
    expected = _get_token()
    if expected:
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if token != expected:
            log.warning("Rejected webhook — invalid bearer token")
            return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not payload:
        log.warning("Rejected webhook — missing or non-JSON body")
        return jsonify({"error": "Bad request"}), 400

    event = payload.get("event", "")
    if not event:
        log.warning("Rejected webhook — missing 'event' field")
        return jsonify({"error": "Missing event"}), 400

    log.info("Received event: %s", event)

    try:
        # Build a fresh client for each request; internal URL for container-to-container
        with PlankaClient() as client:
            handle_event(event, payload, client)
    except PlankaError as e:
        log.error("Planka API error while handling '%s': %s", event, e)
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        log.error("Unexpected error handling '%s': %s", event, e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    return jsonify({"ok": True}), 200


@app.route("/health", methods=["GET"])
def health():
    """Simple liveness check."""
    return jsonify({"status": "ok"}), 200


def run_server(port: int | None = None, debug: bool = False) -> None:
    """Start the Flask webhook server (blocking)."""
    listen_port = port or int(_env("PLANKA_WEBHOOK_PORT") or "5001")
    log.info("Starting webhook server on port %d", listen_port)
    app.run(host="0.0.0.0", port=listen_port, debug=debug)

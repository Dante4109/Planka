"""
Planka REST API client (Planka 2.0+, API v2.0.1).

Auth options (read from .env if not passed explicitly):
  - API key:  PLANKA_API_KEY    → X-Api-Key header  (preferred for automation)
  - Password: PLANKA_USERNAME + PLANKA_PASSWORD → Bearer JWT

Usage:
    from planka_tools.api.client import PlankaClient

    client = PlankaClient()          # reads credentials from .env
    client.login()

    for project in client.get_projects():
        print(project["name"])

    client.logout()

Context-manager usage (auto login/logout):
    with PlankaClient() as client:
        board = client.get_board("1234567890")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


def _load_env(key: str) -> Optional[str]:
    """Read a key from .env, falling back to the real environment."""
    val = os.environ.get(key)
    if val:
        return val
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1]
    return None


class PlankaError(Exception):
    """Raised when the Planka API returns a non-2xx response."""

    def __init__(self, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{status_code}] {error_code}: {message}")


class PlankaClient:
    """
    Thin wrapper around the Planka REST API.

    All methods return plain dicts (the 'item' or 'items' payload from
    the API response), so callers work with standard Python data structures.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.base_url = (base_url or _load_env("BASE_URL") or "").rstrip("/")
        self._api_key = api_key or _load_env("PLANKA_API_KEY")
        self._username = username or _load_env("PLANKA_USERNAME")
        self._password = password or _load_env("PLANKA_PASSWORD")

        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        self._logged_in = False

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self) -> "PlankaClient":
        """Authenticate. Prefers API key; falls back to username/password."""
        if self._api_key:
            self._session.headers["X-Api-Key"] = self._api_key
            self._logged_in = True
            return self

        if self._username and self._password:
            data = self._post(
                "/api/access-tokens",
                json={"emailOrUsername": self._username, "password": self._password},
                _skip_auth_check=True,
            )
            token = data["item"]
            self._session.headers["Authorization"] = f"Bearer {token}"
            self._logged_in = True
            return self

        raise PlankaError(0, "E_NO_CREDENTIALS",
                          "Set PLANKA_API_KEY or PLANKA_USERNAME + PLANKA_PASSWORD in .env")

    def logout(self) -> None:
        """Invalidate the current Bearer token (no-op for API key auth)."""
        if self._logged_in and "Authorization" in self._session.headers:
            self._delete("/api/access-tokens/me")
        self._session.headers.pop("Authorization", None)
        self._session.headers.pop("X-Api-Key", None)
        self._logged_in = False

    def __enter__(self) -> "PlankaClient":
        self.login()
        return self

    def __exit__(self, *_: Any) -> None:
        self.logout()

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def get_projects(self) -> list[dict]:
        """Return all projects visible to the authenticated user."""
        return self._get("/api/projects")["items"]

    def get_project(self, project_id: str) -> dict:
        """Return a single project by ID (includes boards)."""
        return self._get(f"/api/projects/{project_id}")["item"]

    def get_project_boards(self, project_id: str) -> list[dict]:
        """Return all boards in a project."""
        resp = self._get(f"/api/projects/{project_id}")
        return resp.get("included", {}).get("boards", [])

    def create_project(self, name: str, background_type: str = "gradient",
                       background_name: str = "ocean-dive") -> dict:
        return self._post("/api/projects", json={
            "name": name,
            "background": {"type": background_type, "name": background_name},
        })["item"]

    def update_project(self, project_id: str, **fields: Any) -> dict:
        return self._patch(f"/api/projects/{project_id}", json=fields)["item"]

    def delete_project(self, project_id: str) -> dict:
        return self._delete(f"/api/projects/{project_id}")["item"]

    # ------------------------------------------------------------------
    # Boards
    # ------------------------------------------------------------------

    def get_board(self, board_id: str) -> dict:
        """Return a board with sideloaded lists, cards, labels, members."""
        return self._get(f"/api/boards/{board_id}")["item"]

    def get_board_included(self, board_id: str) -> dict:
        """Return the full board response including 'included' relations."""
        return self._get(f"/api/boards/{board_id}")

    def create_board(self, project_id: str, name: str, position: float = 65536.0) -> dict:
        return self._post(f"/api/projects/{project_id}/boards",
                          json={"name": name, "position": position})["item"]

    def update_board(self, board_id: str, **fields: Any) -> dict:
        return self._patch(f"/api/boards/{board_id}", json=fields)["item"]

    def delete_board(self, board_id: str) -> dict:
        return self._delete(f"/api/boards/{board_id}")["item"]

    # ------------------------------------------------------------------
    # Lists
    # ------------------------------------------------------------------

    def get_lists(self, board_id: str) -> list[dict]:
        """Return all lists on a board."""
        return self._get(f"/api/boards/{board_id}").get("included", {}).get("lists", [])

    def create_list(self, board_id: str, name: str, position: float = 65536.0) -> dict:
        return self._post(f"/api/boards/{board_id}/lists",
                          json={"name": name, "position": position})["item"]

    def update_list(self, list_id: str, **fields: Any) -> dict:
        return self._patch(f"/api/lists/{list_id}", json=fields)["item"]

    def delete_list(self, list_id: str) -> dict:
        return self._delete(f"/api/lists/{list_id}")["item"]

    # ------------------------------------------------------------------
    # Cards
    # ------------------------------------------------------------------

    def get_cards(self, board_id: str) -> list[dict]:
        """Return all cards on a board (via board included payload)."""
        return self._get(f"/api/boards/{board_id}").get("included", {}).get("cards", [])

    def get_card(self, card_id: str) -> dict:
        return self._get(f"/api/cards/{card_id}")["item"]

    def create_card(self, list_id: str, name: str, position: float = 65536.0,
                    description: Optional[str] = None, due_date: Optional[str] = None) -> dict:
        payload: dict[str, Any] = {"name": name, "listId": list_id, "position": position}
        if description:
            payload["description"] = description
        if due_date:
            payload["dueDate"] = due_date
        return self._post(f"/api/lists/{list_id}/cards", json=payload)["item"]

    def update_card(self, card_id: str, **fields: Any) -> dict:
        """Update card fields. Common keys: name, description, dueDate, listId, position."""
        return self._patch(f"/api/cards/{card_id}", json=fields)["item"]

    def move_card(self, card_id: str, list_id: str, position: float = 65536.0) -> dict:
        """Move a card to a different list."""
        return self.update_card(card_id, listId=list_id, position=position)

    def duplicate_card(self, card_id: str, position: float = 65536.0) -> dict:
        return self._post(f"/api/cards/{card_id}/duplicate",
                          json={"position": position})["item"]

    def delete_card(self, card_id: str) -> dict:
        return self._delete(f"/api/cards/{card_id}")["item"]

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def get_labels(self, board_id: str) -> list[dict]:
        return self._get(f"/api/boards/{board_id}").get("included", {}).get("labels", [])

    def create_label(self, board_id: str, name: str, color: str = "berry-red") -> dict:
        return self._post(f"/api/boards/{board_id}/labels",
                          json={"name": name, "color": color, "position": 65536.0})["item"]

    def add_label_to_card(self, card_id: str, label_id: str) -> dict:
        return self._post(f"/api/cards/{card_id}/labels", json={"labelId": label_id})["item"]

    def remove_label_from_card(self, card_id: str, label_id: str) -> dict:
        return self._delete(f"/api/cards/{card_id}/labels/{label_id}")["item"]

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def get_comments(self, card_id: str) -> list[dict]:
        return self._get(f"/api/cards/{card_id}/actions")["items"]

    def add_comment(self, card_id: str, text: str) -> dict:
        return self._post(f"/api/cards/{card_id}/comments", json={"text": text})["item"]

    def update_comment(self, comment_id: str, text: str) -> dict:
        return self._patch(f"/api/comments/{comment_id}", json={"text": text})["item"]

    def delete_comment(self, comment_id: str) -> dict:
        return self._delete(f"/api/comments/{comment_id}")["item"]

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def create_task_list(self, card_id: str, name: str, position: float = 65536.0) -> dict:
        return self._post(f"/api/cards/{card_id}/task-lists",
                          json={"name": name, "position": position})["item"]

    def create_task(self, task_list_id: str, name: str, position: float = 65536.0) -> dict:
        return self._post(f"/api/task-lists/{task_list_id}/tasks",
                          json={"name": name, "position": position})["item"]

    def update_task(self, task_id: str, name: Optional[str] = None,
                    is_completed: Optional[bool] = None) -> dict:
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if is_completed is not None:
            payload["isCompleted"] = is_completed
        return self._patch(f"/api/tasks/{task_id}", json=payload)["item"]

    def delete_task(self, task_id: str) -> dict:
        return self._delete(f"/api/tasks/{task_id}")["item"]

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_me(self) -> dict:
        return self._get("/api/users/me")["item"]

    def get_users(self) -> list[dict]:
        return self._get("/api/users")["items"]

    def get_user(self, user_id: str) -> dict:
        return self._get(f"/api/users/{user_id}")["item"]

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def get_notifications(self) -> list[dict]:
        return self._get("/api/notifications")["items"]

    def mark_notifications_read(self) -> None:
        self._post("/api/notifications/read-all", json={})

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def find_project(self, name: str) -> Optional[dict]:
        """Return the first project matching the given name, or None."""
        return next((p for p in self.get_projects() if p["name"] == name), None)

    def find_board(self, project_id: str, name: str) -> Optional[dict]:
        """Return the first board in a project matching the given name, or None."""
        return next((b for b in self.get_project_boards(project_id) if b["name"] == name), None)

    def find_list(self, board_id: str, name: str) -> Optional[dict]:
        """Return the first list on a board matching the given name, or None."""
        return next((l for l in self.get_lists(board_id) if l["name"] == name), None)

    def find_card(self, board_id: str, name: str) -> Optional[dict]:
        """Return the first card on a board matching the given name, or None."""
        return next((c for c in self.get_cards(board_id) if c["name"] == name), None)

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _raise_for_status(self, response: requests.Response) -> dict:
        if response.ok:
            if not response.content or not response.content.strip():
                return {}
            try:
                return response.json()
            except Exception:
                return {}
        try:
            body = response.json()
            # Planka error format: {"code": "E_NOT_FOUND", "message": "..."}
            error_code = body.get("code", body.get("error", {}).get("type", "E_UNKNOWN"))
            message = body.get("message", body.get("error", {}).get("message", response.text))
        except Exception:
            error_code = "E_UNKNOWN"
            message = response.text
        raise PlankaError(response.status_code, error_code, message)

    def _get(self, path: str) -> dict:
        return self._raise_for_status(self._session.get(self._url(path)))

    def _post(self, path: str, json: dict, _skip_auth_check: bool = False) -> dict:
        return self._raise_for_status(self._session.post(self._url(path), json=json))

    def _patch(self, path: str, json: dict) -> dict:
        return self._raise_for_status(self._session.patch(self._url(path), json=json))

    def _delete(self, path: str) -> dict:
        return self._raise_for_status(self._session.delete(self._url(path)))

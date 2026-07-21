"""Unit tests for PlankaClient (api/client.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from planka_tools.api.client import PlankaClient, PlankaError


def _ok_response(payload: dict) -> MagicMock:
    """Return a mock requests.Response that looks like a successful JSON response."""
    resp = MagicMock()
    resp.ok = True
    resp.content = b"x"
    resp.json.return_value = payload
    return resp


def _error_response(status: int, code: str, message: str) -> MagicMock:
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status
    resp.json.return_value = {"code": code, "message": message}
    return resp


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    def test_api_key_sets_header(self):
        client = PlankaClient(base_url="http://planka.test", api_key="test-key-123")
        client.login()
        assert client._session.headers.get("X-Api-Key") == "test-key-123"
        assert client._logged_in is True

    def test_api_key_does_not_set_bearer(self):
        client = PlankaClient(base_url="http://planka.test", api_key="test-key-123")
        client.login()
        assert "Authorization" not in client._session.headers

    def test_password_auth_posts_and_sets_bearer(self):
        # Patch _load_env so the local .env's PLANKA_API_KEY doesn't take precedence
        with patch("planka_tools.api.client._load_env", return_value=None):
            client = PlankaClient(
                base_url="http://planka.test", username="admin@test.com", password="secret"
            )
        mock_resp = _ok_response({"item": "jwt-abc"})
        with patch.object(client._session, "post", return_value=mock_resp) as mock_post:
            client.login()
        mock_post.assert_called_once()
        call_url = mock_post.call_args.args[0]
        assert call_url == "http://planka.test/api/access-tokens"
        assert client._session.headers.get("Authorization") == "Bearer jwt-abc"
        assert client._logged_in is True

    def test_no_credentials_raises_planka_error(self):
        client = PlankaClient(base_url="http://planka.test")
        client._api_key = None
        client._username = None
        client._password = None
        with pytest.raises(PlankaError) as exc_info:
            client.login()
        assert exc_info.value.error_code == "E_NO_CREDENTIALS"

    def test_context_manager_logs_in_and_out(self):
        client = PlankaClient(base_url="http://planka.test", api_key="key")
        with client as c:
            assert c._logged_in is True
        assert client._logged_in is False

    def test_logout_removes_api_key_header(self):
        client = PlankaClient(base_url="http://planka.test", api_key="key")
        client.login()
        assert "X-Api-Key" in client._session.headers
        client.logout()
        assert "X-Api-Key" not in client._session.headers


# ---------------------------------------------------------------------------
# HTTP helpers / error handling
# ---------------------------------------------------------------------------

class TestRaiseForStatus:
    def _client(self):
        c = PlankaClient(base_url="http://planka.test", api_key="key")
        c.login()
        return c

    def test_200_returns_parsed_json(self):
        client = self._client()
        resp = _ok_response({"items": [1, 2, 3]})
        with patch.object(client._session, "get", return_value=resp):
            result = client._get("/api/test")
        assert result == {"items": [1, 2, 3]}

    def test_404_raises_planka_error(self):
        client = self._client()
        resp = _error_response(404, "E_NOT_FOUND", "Not found")
        with patch.object(client._session, "get", return_value=resp):
            with pytest.raises(PlankaError) as exc_info:
                client._get("/api/missing")
        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "E_NOT_FOUND"

    def test_400_raises_planka_error_with_correct_code(self):
        client = self._client()
        resp = _error_response(400, "E_MISSING_OR_INVALID_PARAMS", "Bad params")
        with patch.object(client._session, "post", return_value=resp):
            with pytest.raises(PlankaError) as exc_info:
                client._post("/api/boards", json={"name": ""})
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "E_MISSING_OR_INVALID_PARAMS"

    def test_empty_response_returns_empty_dict(self):
        client = self._client()
        resp = MagicMock()
        resp.ok = True
        resp.content = b""
        with patch.object(client._session, "get", return_value=resp):
            result = client._get("/api/ping")
        assert result == {}

    def test_planka_error_str_includes_status_and_code(self):
        err = PlankaError(403, "E_FORBIDDEN", "No access")
        assert "403" in str(err)
        assert "E_FORBIDDEN" in str(err)


# ---------------------------------------------------------------------------
# Specific endpoint contracts
# ---------------------------------------------------------------------------

class TestEndpointContracts:
    def _client(self):
        c = PlankaClient(base_url="http://planka.test", api_key="key")
        c.login()
        return c

    def test_add_label_to_card_uses_card_labels_endpoint(self):
        client = self._client()
        resp = _ok_response({"item": {"id": "cl-1"}})
        with patch.object(client._session, "post", return_value=resp) as mock_post:
            client.add_label_to_card("card-1", "label-1")
        url = mock_post.call_args.args[0]
        assert url == "http://planka.test/api/cards/card-1/card-labels"
        assert mock_post.call_args.kwargs["json"] == {"labelId": "label-1"}

    def test_set_custom_field_value_builds_correct_url(self):
        client = self._client()
        resp = _ok_response({"item": {"id": "cfv-1", "content": "High"}})
        with patch.object(client._session, "patch", return_value=resp) as mock_patch:
            client.set_custom_field_value("card-1", "grp-1", "fld-1", "High")
        url = mock_patch.call_args.args[0]
        expected = (
            "http://planka.test/api/cards/card-1/custom-field-values"
            "/customFieldGroupId:grp-1:customFieldId:fld-1"
        )
        assert url == expected
        assert mock_patch.call_args.kwargs["json"] == {"content": "High"}

    def test_remove_member_from_card_uses_delete(self):
        client = self._client()
        resp = _ok_response({"item": {"id": "cm-1"}})
        with patch.object(client._session, "delete", return_value=resp) as mock_del:
            client.remove_member_from_card("card-1", "user-1")
        url = mock_del.call_args.args[0]
        assert url == "http://planka.test/api/cards/card-1/card-memberships/userId:user-1"

    def test_add_member_to_card_uses_post(self):
        client = self._client()
        resp = _ok_response({"item": {"id": "cm-1", "cardId": "card-1", "userId": "user-1"}})
        with patch.object(client._session, "post", return_value=resp) as mock_post:
            client.add_member_to_card("card-1", "user-1")
        url = mock_post.call_args.args[0]
        assert url == "http://planka.test/api/cards/card-1/card-memberships"
        assert mock_post.call_args.kwargs["json"] == {"userId": "user-1"}

    def test_create_card_includes_type_and_list_id(self):
        client = self._client()
        resp = _ok_response({"item": {"id": "card-new", "name": "My Card"}})
        with patch.object(client._session, "post", return_value=resp) as mock_post:
            client.create_card("list-1", name="My Card", position=65536.0)
        payload = mock_post.call_args.kwargs["json"]
        assert payload["listId"] == "list-1"
        assert payload["type"] == "project"
        assert payload["name"] == "My Card"

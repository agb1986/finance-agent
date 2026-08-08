"""Tests for common.http_client.HttpClient."""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests
from common.http_client import RETRY_STATUSES, USER_AGENT, HttpClient


@pytest.fixture(autouse=True)
def reset_logger():
    yield
    logging.getLogger("finance_agent").handlers.clear()


class TestHttpClientInit:
    def test_base_url_trailing_slash_stripped(self):
        client = HttpClient("https://example.com/")
        assert client.base_url == "https://example.com"

    def test_headers_applied_to_session(self):
        client = HttpClient("https://example.com", headers={"Authorization": "key123"})
        assert client.session.headers["Authorization"] == "key123"

    def test_no_headers_ok(self):
        client = HttpClient("https://example.com")
        assert "Authorization" not in client.session.headers

    def test_default_timeout(self):
        client = HttpClient("https://example.com")
        assert client.timeout == 30

    def test_custom_timeout(self):
        client = HttpClient("https://example.com", timeout=10)
        assert client.timeout == 10

    def test_user_agent_set(self):
        client = HttpClient("https://example.com")
        assert client.session.headers["User-Agent"] == USER_AGENT

    def test_custom_headers_do_not_remove_user_agent(self):
        client = HttpClient("https://example.com", headers={"Authorization": "key123"})
        assert client.session.headers["User-Agent"] == USER_AGENT

    def test_retry_adapter_mounted(self):
        client = HttpClient("https://example.com")
        for prefix in ("https://", "http://"):
            retry = client.session.get_adapter(f"{prefix}example.com").max_retries
            assert retry.total == 3
            assert set(RETRY_STATUSES) <= set(retry.status_forcelist)
            assert "POST" in retry.allowed_methods

    def test_retry_count_configurable(self):
        client = HttpClient("https://example.com", retries=5)
        retry = client.session.get_adapter("https://example.com").max_retries
        assert retry.total == 5


class TestHttpClientGet:
    def _client(self, headers: dict | None = None) -> HttpClient:
        return HttpClient("https://example.com", headers=headers)

    def test_returns_parsed_json(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}
        with patch.object(client.session, "get", return_value=mock_response) as mock_get:
            result = client.get("/some/path")

        mock_get.assert_called_once_with("https://example.com/some/path", params=None, timeout=30)
        assert result == {"key": "value"}

    def test_leading_slash_on_path_handled(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        with patch.object(client.session, "get", return_value=mock_response) as mock_get:
            client.get("/api/v0/resource")

        url_called = mock_get.call_args[0][0]
        assert url_called == "https://example.com/api/v0/resource"

    def test_params_forwarded(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.json.return_value = []
        with patch.object(client.session, "get", return_value=mock_response) as mock_get:
            client.get("/path", params={"limit": 10})

        assert mock_get.call_args[1]["params"] == {"limit": 10}

    def test_raises_on_http_error(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403")
        with patch.object(client.session, "get", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                client.get("/protected")

    def test_returns_list_response(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        with patch.object(client.session, "get", return_value=mock_response):
            result = client.get("/items")

        assert isinstance(result, list)
        assert len(result) == 2


class TestHttpClientPost:
    def _client(self) -> HttpClient:
        return HttpClient("https://example.com")

    def test_returns_parsed_json(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0, "result": {}}
        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            result = client.post("/some/path", json={"method": "test"})

        mock_post.assert_called_once_with(
            "https://example.com/some/path", json={"method": "test"}, timeout=30
        )
        assert result == {"code": 0, "result": {}}

    def test_leading_slash_on_path_handled(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            client.post("/api/v1/private/method", json={})

        url_called = mock_post.call_args[0][0]
        assert url_called == "https://example.com/api/v1/private/method"

    def test_raises_on_http_error(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("401")
        with patch.object(client.session, "post", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                client.post("/private")

    def test_none_body_allowed(self):
        client = self._client()
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            client.post("/path")

        assert mock_post.call_args[1]["json"] is None

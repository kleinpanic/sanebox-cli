"""Tests for SaneBox CLI API module."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from sanebox_cli.api import SaneBoxAPI, SaneBoxFolder
from sanebox_cli.auth import AuthManager, SaneBoxCredentials


def test_folder_dataclass():
    """Test SaneBoxFolder dataclass."""
    folder = SaneBoxFolder(name="SaneLater", count=42, unread=5)
    assert folder.name == "SaneLater"
    assert folder.count == 42
    assert folder.unread == 5


def test_folders_list():
    """Test FOLDERS constant."""
    assert "SaneLater" in SaneBoxAPI.FOLDERS
    assert "SaneBlackHole" in SaneBoxAPI.FOLDERS
    assert "SaneNews" in SaneBoxAPI.FOLDERS


def _make_api_with_mock_auth():
    """Helper: create API instance with mocked auth."""
    mock_auth = MagicMock(spec=AuthManager)
    mock_auth.is_authenticated.return_value = True
    mock_auth.get_auth_headers.return_value = {"Authorization": "Bearer test-token"}
    mock_auth.credentials = SaneBoxCredentials(
        auth_method="session",
        session_cookie="test-cookie",
        active_account="you@example.com",
    )
    api = SaneBoxAPI(auth_manager=mock_auth)
    return api


@patch("sanebox_cli.api.requests.request")
def test_train(mock_request):
    """Test train method."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    api = _make_api_with_mock_auth()
    result = api.train("sender@example.com", "SaneLater")
    assert result is True


@patch("sanebox_cli.api.requests.request")
def test_blacklist_add(mock_request):
    """Test blacklist_add delegates to train with SaneBlackHole."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    api = _make_api_with_mock_auth()
    result = api.blacklist_add("spam@example.com")
    assert result is True


@patch("sanebox_cli.api.requests.request")
def test_blacklist_list(mock_request):
    """Test blacklist_list returns emails."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"emails": ["spam@example.com", "junk@test.com"]}
    mock_request.return_value = mock_response

    api = _make_api_with_mock_auth()
    emails = api.blacklist_list()
    assert "spam@example.com" in emails
    assert len(emails) == 2


@patch("sanebox_cli.api.requests.request")
def test_train_invalid_folder_warns(mock_request, capsys):
    """Test train warns on non-standard folder."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_request.return_value = mock_response

    api = _make_api_with_mock_auth()
    api.train("sender@example.com", "NotARealFolder")
    # Should still proceed (just warn)


@patch("sanebox_cli.api.requests.request")
def test_request_raises_on_unauthenticated(mock_request):
    """Test _request raises when not authenticated."""
    mock_auth = MagicMock(spec=AuthManager)
    mock_auth.is_authenticated.return_value = False
    api = SaneBoxAPI(auth_manager=mock_auth)

    with pytest.raises(ValueError, match="Not authenticated"):
        api._request("GET", "/test")

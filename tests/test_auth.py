"""Tests for SaneBox CLI auth module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch


import sanebox_cli.auth as auth_module
from sanebox_cli.auth import AuthManager, SaneBoxCredentials, get_allowed_accounts


# ---------------------------------------------------------------------------
# get_allowed_accounts
# ---------------------------------------------------------------------------


def test_allowed_accounts_from_env(monkeypatch):
    monkeypatch.setenv("SANEBOX_ALLOWED_ACCOUNTS", "a@x.com, b@y.com")
    accounts = get_allowed_accounts()
    assert "a@x.com" in accounts
    assert "b@y.com" in accounts


def test_allowed_accounts_empty_env(monkeypatch):
    monkeypatch.delenv("SANEBOX_ALLOWED_ACCOUNTS", raising=False)
    # patch CONFIG_FILE so it doesn't exist
    with tempfile.TemporaryDirectory() as td:
        old = auth_module.CONFIG_FILE
        auth_module.CONFIG_FILE = Path(td) / "nonexistent.json"
        try:
            accounts = get_allowed_accounts()
            assert accounts == []
        finally:
            auth_module.CONFIG_FILE = old


def test_allowed_accounts_from_config_file(monkeypatch, tmp_path):
    monkeypatch.delenv("SANEBOX_ALLOWED_ACCOUNTS", raising=False)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"allowed_accounts": ["test@example.com"]}))

    old = auth_module.CONFIG_FILE
    auth_module.CONFIG_FILE = cfg
    try:
        accounts = get_allowed_accounts()
        assert "test@example.com" in accounts
    finally:
        auth_module.CONFIG_FILE = old


# ---------------------------------------------------------------------------
# SaneBoxCredentials
# ---------------------------------------------------------------------------


def test_credentials_dataclass():
    creds = SaneBoxCredentials(auth_method="oauth", access_token="tok")
    assert creds.auth_method == "oauth"
    assert creds.access_token == "tok"
    assert creds.accounts == []
    assert creds.created_at is not None


# ---------------------------------------------------------------------------
# AuthManager
# ---------------------------------------------------------------------------


def _temp_auth(tmp_path):
    """Return an AuthManager using tmp_path for credentials."""
    old_creds = auth_module.CREDENTIALS_FILE
    auth_module.CREDENTIALS_FILE = tmp_path / "credentials.json"
    mgr = AuthManager()
    return mgr, old_creds


def test_auth_manager_not_authenticated(tmp_path):
    old = auth_module.CREDENTIALS_FILE
    auth_module.CREDENTIALS_FILE = tmp_path / "credentials.json"
    try:
        auth = AuthManager()
        assert not auth.is_authenticated()
        assert auth.credentials is None
    finally:
        auth_module.CREDENTIALS_FILE = old


def test_auth_manager_save_load(tmp_path):
    old = auth_module.CREDENTIALS_FILE
    auth_module.CREDENTIALS_FILE = tmp_path / "credentials.json"
    try:
        auth1 = AuthManager()
        auth1.credentials = SaneBoxCredentials(
            auth_method="session",
            session_cookie="cookie=abc123",
            active_account="test@example.com",
        )
        auth1._save_credentials()

        auth2 = AuthManager()
        assert auth2.is_authenticated()
        assert auth2.credentials.session_cookie == "cookie=abc123"
        assert auth2.credentials.active_account == "test@example.com"

        # Credentials file should be mode 600
        mode = oct(tmp_path.joinpath("credentials.json").stat().st_mode)[-3:]
        assert mode == "600"
    finally:
        auth_module.CREDENTIALS_FILE = old


def test_login_signin_success(tmp_path, monkeypatch):
    """login_signin should store session cookie on success."""
    old = auth_module.CREDENTIALS_FILE
    auth_module.CREDENTIALS_FILE = tmp_path / "credentials.json"

    mock_session = MagicMock()
    mock_get_resp = Mock(status_code=200, text="<html></html>", url=auth_module.SANEBOX_LOGIN_URL)
    mock_post_resp = Mock(status_code=200, url="https://www.sanebox.com/dashboard", text="")
    mock_session.get.return_value = mock_get_resp
    mock_session.post.return_value = mock_post_resp
    mock_cookies = MagicMock()
    mock_cookies.get = Mock(return_value="sess_abc")
    mock_cookies.__iter__ = Mock(return_value=iter([Mock(name="_sanebox_session", value="sess_abc")]))
    mock_cookies.__bool__ = Mock(return_value=True)
    mock_session.cookies = mock_cookies

    with patch("sanebox_cli.auth.requests.Session", return_value=mock_session):
        auth = AuthManager()
        result = auth.login_signin("test@example.com", "password123")

    assert result is True
    assert auth.credentials is not None
    assert auth.credentials.auth_method == "signin"
    assert auth.credentials.active_account == "test@example.com"

    auth_module.CREDENTIALS_FILE = old

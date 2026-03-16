"""Tests for SaneBox CLI auth module."""

from pathlib import Path

from sanebox_cli.auth import AuthManager, SaneBoxCredentials


def test_credentials_dataclass():
    """Test SaneBoxCredentials dataclass."""
    creds = SaneBoxCredentials(auth_method="oauth", access_token="test-token")

    assert creds.auth_method == "oauth"
    assert creds.access_token == "test-token"
    assert creds.accounts == []
    assert creds.created_at is not None


def test_auth_manager_not_authenticated():
    """Test AuthManager when not logged in."""
    # Use a temp config dir
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Override config path
        import sanebox_cli.auth

        old_path = sanebox_cli.auth.CREDENTIALS_FILE
        sanebox_cli.auth.CREDENTIALS_FILE = Path(tmpdir) / "credentials.json"

        try:
            auth = AuthManager()
            assert not auth.is_authenticated()
            assert auth.credentials is None
        finally:
            sanebox_cli.auth.CREDENTIALS_FILE = old_path


def test_auth_manager_save_load():
    """Test saving and loading credentials."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        import sanebox_cli.auth

        old_path = sanebox_cli.auth.CREDENTIALS_FILE
        sanebox_cli.auth.CREDENTIALS_FILE = Path(tmpdir) / "credentials.json"

        try:
            # Save credentials
            auth1 = AuthManager()
            auth1.credentials = SaneBoxCredentials(
                auth_method="session",
                session_cookie="test-cookie",
                active_account="test@example.com",
            )
            auth1._save_credentials()

            # Load credentials
            auth2 = AuthManager()
            assert auth2.is_authenticated()
            assert auth2.credentials.auth_method == "session"
            assert auth2.credentials.session_cookie == "test-cookie"
            assert auth2.credentials.active_account == "test@example.com"
        finally:
            sanebox_cli.auth.CREDENTIALS_FILE = old_path

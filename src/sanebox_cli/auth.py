"""
SaneBox Authentication Manager.

Supports two auth methods:
1. OAuth flow (official API - requires client_id)
2. Session auth (extract session cookie from browser)
"""

import os
import json
import webbrowser
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

import requests
from rich.console import Console
from rich.prompt import Prompt

console = Console()

# Accounts this CLI is allowed to manage (never touch others)
ALLOWED_ACCOUNTS = [
    "rodie105@gmail.com",
    "scollin93@vt.edu",
    "kleinpanic@gmail.com",
]

# SaneBox API endpoints
SANEBOX_API_BASE = "https://www.sanebox.com"
SANEBOX_OAUTH_AUTHORIZE = f"{SANEBOX_API_BASE}/api/oauth/authorize"
SANEBOX_OAUTH_TOKEN = f"{SANEBOX_API_BASE}/api/oauth/token"

# Config paths
CONFIG_DIR = Path.home() / ".config" / "sanebox-cli"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


@dataclass
class SaneBoxCredentials:
    """Stored credentials for SaneBox."""

    auth_method: str  # "oauth" or "session"
    access_token: Optional[str] = None
    session_cookie: Optional[str] = None
    active_account: Optional[str] = None
    accounts: list[str] = None
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.accounts is None:
            self.accounts = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class AuthManager:
    """Manage SaneBox authentication."""

    def __init__(self):
        self.credentials: Optional[SaneBoxCredentials] = None
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load credentials from file."""
        if CREDENTIALS_FILE.exists():
            try:
                data = json.loads(CREDENTIALS_FILE.read_text())
                self.credentials = SaneBoxCredentials(**data)
            except (json.JSONDecodeError, TypeError):
                self.credentials = None

    def _save_credentials(self) -> None:
        """Save credentials to file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(json.dumps(self.credentials.__dict__, indent=2))
        # Secure the file
        os.chmod(CREDENTIALS_FILE, 0o600)

    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        if not self.credentials:
            return False
        return bool(self.credentials.access_token or self.credentials.session_cookie)

    def get_auth_headers(self) -> dict:
        """Get authorization headers for API requests."""
        if not self.credentials:
            raise ValueError("Not authenticated. Run 'sanebox auth login'")

        if self.credentials.auth_method == "oauth":
            return {
                "Authorization": f"Bearer {self.credentials.access_token}",
                "Content-Type": "application/json",
            }
        else:  # session
            return {
                "Cookie": self.credentials.session_cookie,
                "Content-Type": "application/json",
            }

    def login_oauth(self, client_id: str, client_secret: str = "") -> bool:
        """
        Login using OAuth flow.

        Args:
            client_id: OAuth client ID from SaneBox
            client_secret: OAuth client secret (if required)

        Returns:
            True if login successful
        """
        console.print("[cyan]Starting OAuth flow...[/cyan]")

        # Build authorization URL
        # Note: Actual OAuth params may differ - adjust based on SaneBox docs
        auth_url = (
            f"{SANEBOX_OAUTH_AUTHORIZE}"
            f"?client_id={client_id}"
            f"&response_type=code"
            f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
        )

        console.print("\n[bold]Opening browser for authorization...[/bold]")
        console.print(f"[dim]{auth_url}[/dim]\n")

        webbrowser.open(auth_url)

        # Wait for user to enter code
        auth_code = Prompt.ask("Paste the authorization code from the browser")

        if not auth_code:
            console.print("[red]No code provided[/red]")
            return False

        # Exchange code for access token
        try:
            response = requests.post(
                SANEBOX_OAUTH_TOKEN,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": auth_code,
                    "grant_type": "authorization_code",
                    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                },
            )

            if response.status_code == 200:
                token_data = response.json()
                self.credentials = SaneBoxCredentials(
                    auth_method="oauth",
                    access_token=token_data.get("access_token"),
                    accounts=token_data.get("accounts", []),
                )
                self._save_credentials()
                console.print("[green]✓ OAuth login successful![/green]")
                return True
            else:
                console.print(f"[red]OAuth error: {response.text}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]OAuth failed: {e}[/red]")
            return False

    def login_session(self, session_cookie: str) -> bool:
        """
        Login using session cookie extracted from browser.

        Args:
            session_cookie: Full cookie string from browser (e.g., "_session=abc123")

        Returns:
            True if login successful
        """
        console.print("[cyan]Validating session cookie...[/cyan]")

        # Test the session by making a request to SaneBox
        try:
            response = requests.get(
                f"{SANEBOX_API_BASE}/dashboard",
                headers={"Cookie": session_cookie},
                allow_redirects=False,
            )

            # If we get a 200 or redirect to dashboard, session is valid
            if response.status_code in [200, 302]:
                self.credentials = SaneBoxCredentials(
                    auth_method="session",
                    session_cookie=session_cookie,
                    accounts=[],  # Will be populated on first API call
                )
                self._save_credentials()
                console.print("[green]✓ Session login successful![/green]")
                return True
            else:
                console.print(f"[red]Invalid session: status {response.status_code}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Session validation failed: {e}[/red]")
            return False

    def logout(self) -> None:
        """Clear stored credentials."""
        self.credentials = None
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
        console.print("[green]Logged out successfully[/green]")

    def status(self) -> dict:
        """Get authentication status."""
        if not self.credentials:
            return {"authenticated": False, "message": "Not logged in. Run 'sanebox auth login'"}

        return {
            "authenticated": True,
            "auth_method": self.credentials.auth_method,
            "active_account": self.credentials.active_account,
            "accounts": self.credentials.accounts,
            "created_at": self.credentials.created_at,
        }

    def set_active_account(self, email: str) -> None:
        """Set the active email account (only allowed accounts)."""
        if not self.credentials:
            raise ValueError("Not authenticated")

        if email not in ALLOWED_ACCOUNTS:
            raise ValueError(
                f"Account '{email}' is not in the allowed list.\n"
                f"Allowed accounts: {', '.join(ALLOWED_ACCOUNTS)}"
            )

        self.credentials.active_account = email
        self._save_credentials()
        console.print(f"[green]Active account set to: {email}[/green]")

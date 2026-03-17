"""
SaneBox Authentication Manager.

Supports two auth methods:
1. OAuth flow (official API - requires client_id)
2. Web signin (email + password → extracts session cookie automatically)

Allowed accounts are loaded from config, never hardcoded.
"""

import os
import json
import webbrowser
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

import requests
from rich.console import Console
from rich.prompt import Prompt

console = Console()

# SaneBox endpoints
SANEBOX_BASE = "https://www.sanebox.com"
SANEBOX_LOGIN_URL = f"{SANEBOX_BASE}/login"
SANEBOX_OAUTH_AUTHORIZE = f"{SANEBOX_BASE}/api/oauth/authorize"
SANEBOX_OAUTH_TOKEN = f"{SANEBOX_BASE}/api/oauth/token"

# Config paths
CONFIG_DIR = Path.home() / ".config" / "sanebox-cli"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _load_allowed_accounts() -> list[str]:
    """
    Load the allowed account list from config or env — never hardcoded.

    Priority:
      1. SANEBOX_ALLOWED_ACCOUNTS env var (comma-separated)
      2. ~/.config/sanebox-cli/config.json  { "allowed_accounts": [...] }
      3. Empty list (no restriction — all authenticated accounts allowed)
    """
    env_val = os.environ.get("SANEBOX_ALLOWED_ACCOUNTS", "").strip()
    if env_val:
        return [a.strip() for a in env_val.split(",") if a.strip()]

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            accts = data.get("allowed_accounts", [])
            if isinstance(accts, list):
                return accts
        except (json.JSONDecodeError, TypeError):
            pass

    return []  # no restriction


def get_allowed_accounts() -> list[str]:
    """Public accessor — re-evaluated each call so env changes take effect."""
    return _load_allowed_accounts()


@dataclass
class SaneBoxCredentials:
    """Stored credentials for SaneBox."""

    auth_method: str  # "oauth" | "session" | "signin"
    access_token: Optional[str] = None
    session_cookie: Optional[str] = None
    active_account: Optional[str] = None
    accounts: list[str] = field(default_factory=list)
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class AuthManager:
    """Manage SaneBox authentication."""

    def __init__(self):
        self.credentials: Optional[SaneBoxCredentials] = None
        self._load_credentials()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_credentials(self) -> None:
        if CREDENTIALS_FILE.exists():
            try:
                data = json.loads(CREDENTIALS_FILE.read_text())
                self.credentials = SaneBoxCredentials(**data)
            except (json.JSONDecodeError, TypeError):
                self.credentials = None

    def _save_credentials(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(json.dumps(self.credentials.__dict__, indent=2))
        os.chmod(CREDENTIALS_FILE, 0o600)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def is_authenticated(self) -> bool:
        if not self.credentials:
            return False
        return bool(self.credentials.access_token or self.credentials.session_cookie)

    def get_auth_headers(self) -> dict:
        if not self.credentials:
            raise ValueError("Not authenticated. Run 'sanebox auth login'")
        if self.credentials.auth_method == "oauth":
            return {
                "Authorization": f"Bearer {self.credentials.access_token}",
                "Content-Type": "application/json",
            }
        # session / signin
        return {
            "Cookie": self.credentials.session_cookie,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Sign-in via web (email + password → session cookie)
    # ------------------------------------------------------------------

    def login_signin(self, email: str, password: str) -> bool:
        """
        Authenticate by POSTing credentials to SaneBox login form,
        then extracting the session cookie from the response.

        This is the practical fallback when no OAuth client_id is available.
        """
        console.print("[cyan]Signing in to SaneBox...[/cyan]")

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/html, */*",
                "Referer": SANEBOX_LOGIN_URL,
                "Origin": SANEBOX_BASE,
            }
        )

        # Step 1: GET login page to pick up any CSRF token
        try:
            get_resp = session.get(SANEBOX_LOGIN_URL, timeout=15)
            get_resp.raise_for_status()
        except requests.RequestException as exc:
            console.print(f"[red]Failed to reach SaneBox login page: {exc}[/red]")
            return False

        # Extract CSRF token if present (common Rails pattern)
        csrf_token = None
        try:
            from html.parser import HTMLParser

            class _CSRFParser(HTMLParser):
                token = None

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == "input" and attrs_dict.get("name") in (
                        "authenticity_token",
                        "_token",
                        "csrf_token",
                    ):
                        self.token = attrs_dict.get("value")
                    elif tag == "meta" and attrs_dict.get("name") == "csrf-token":
                        self.token = attrs_dict.get("content")

            parser = _CSRFParser()
            parser.feed(get_resp.text)
            csrf_token = parser.token
        except Exception:
            pass

        # Step 2: POST login form
        payload: dict = {"email": email, "password": password}
        if csrf_token:
            payload["authenticity_token"] = csrf_token

        try:
            post_resp = session.post(
                SANEBOX_LOGIN_URL,
                data=payload,
                allow_redirects=True,
                timeout=15,
            )
        except requests.RequestException as exc:
            console.print(f"[red]Login request failed: {exc}[/red]")
            return False

        # Step 3: Extract session cookie
        cookie_names = ["_sanebox_session", "_session", "session", "remember_user_token"]
        session_cookie_str = None

        for name in cookie_names:
            val = session.cookies.get(name)
            if val:
                session_cookie_str = f"{name}={val}"
                break

        # Fallback: grab all cookies as a header string
        if not session_cookie_str and session.cookies:
            session_cookie_str = "; ".join(f"{c.name}={c.value}" for c in session.cookies)

        if not session_cookie_str:
            console.print(
                "[red]Login may have failed — no session cookie returned.[/red]\n"
                "[dim]Check your email/password and try again, or use "
                "'sanebox auth login --session' to paste a cookie manually.[/dim]"
            )
            return False

        # Check we landed somewhere authenticated (not back on login page)
        if SANEBOX_LOGIN_URL in post_resp.url and post_resp.status_code == 200:
            # Likely redirected back to login = bad credentials
            if "invalid" in post_resp.text.lower() or "incorrect" in post_resp.text.lower():
                console.print("[red]Invalid email or password.[/red]")
                return False

        self.credentials = SaneBoxCredentials(
            auth_method="signin",
            session_cookie=session_cookie_str,
            active_account=email,
            accounts=[email],
        )
        self._save_credentials()
        console.print(f"[green]✓ Signed in as {email}[/green]")
        return True

    # ------------------------------------------------------------------
    # Session cookie (manual paste from browser DevTools)
    # ------------------------------------------------------------------

    def login_session(self, session_cookie: str) -> bool:
        """Login using session cookie extracted from browser."""
        console.print("[cyan]Validating session cookie...[/cyan]")
        try:
            response = requests.get(
                f"{SANEBOX_BASE}/dashboard",
                headers={"Cookie": session_cookie},
                allow_redirects=False,
                timeout=10,
            )
            if response.status_code in [200, 302]:
                self.credentials = SaneBoxCredentials(
                    auth_method="session",
                    session_cookie=session_cookie,
                    accounts=[],
                )
                self._save_credentials()
                console.print("[green]✓ Session login successful![/green]")
                return True
            else:
                console.print(f"[red]Invalid session: status {response.status_code}[/red]")
                return False
        except Exception as exc:
            console.print(f"[red]Session validation failed: {exc}[/red]")
            return False

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    def login_oauth(self, client_id: str, client_secret: str = "") -> bool:
        """Login using OAuth flow (requires client_id from SaneBox support)."""
        console.print("[cyan]Starting OAuth flow...[/cyan]")

        auth_url = (
            f"{SANEBOX_OAUTH_AUTHORIZE}"
            f"?client_id={client_id}"
            f"&response_type=code"
            f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
        )

        console.print("\n[bold]Opening browser for authorization...[/bold]")
        console.print(f"[dim]{auth_url}[/dim]\n")
        webbrowser.open(auth_url)

        auth_code = Prompt.ask("Paste the authorization code from the browser")
        if not auth_code:
            console.print("[red]No code provided[/red]")
            return False

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
                timeout=15,
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
        except Exception as exc:
            console.print(f"[red]OAuth failed: {exc}[/red]")
            return False

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def set_active_account(self, email: str) -> None:
        """Set the active email account."""
        if not self.credentials:
            raise ValueError("Not authenticated")

        allowed = get_allowed_accounts()
        if allowed and email not in allowed:
            raise ValueError(
                f"Account '{email}' is not in your allowed accounts list.\n"
                f"Add it via: SANEBOX_ALLOWED_ACCOUNTS env var or "
                f"~/.config/sanebox-cli/config.json"
            )

        self.credentials.active_account = email
        self._save_credentials()
        console.print(f"[green]Active account set to: {email}[/green]")

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

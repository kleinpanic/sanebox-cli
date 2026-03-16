"""
SaneBox API Client.

Provides methods to interact with SaneBox API:
- Train senders to folders
- Manage blacklist
- View digest
- Get stats

NOTE: Actual API endpoint paths are placeholders until SaneBox support
responds with official API documentation. Update the path strings once
we have the real endpoints.
"""

from typing import Optional
from dataclasses import dataclass

import requests
from rich.console import Console

from sanebox_cli.auth import AuthManager, ALLOWED_ACCOUNTS

console = Console()

# SaneBox API base (actual endpoints TBD from support)
API_BASE = "https://www.sanebox.com/api"


@dataclass
class SaneBoxFolder:
    """Represents a SaneBox folder."""

    name: str
    count: int
    unread: int


class SaneBoxAPI:
    """Client for SaneBox API."""

    FOLDERS = [
        "SaneLater",
        "SaneNews",
        "SaneBlackHole",
        "SaneNoReplies",
        "SaneCC",
        "SaneBulk",
        "SaneNotSpam",
    ]

    def __init__(self, auth_manager: Optional[AuthManager] = None):
        self.auth = auth_manager or AuthManager()

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make authenticated request to SaneBox API."""
        if not self.auth.is_authenticated():
            raise ValueError("Not authenticated. Run 'sanebox auth login'")

        # Enforce account allowlist
        active = getattr(self.auth.credentials, "active_account", None)
        if active and active not in ALLOWED_ACCOUNTS:
            raise ValueError(
                f"Account '{active}' is not in the allowed list. "
                "Run 'sanebox accounts use <email>' to select an allowed account."
            )

        headers = self.auth.get_auth_headers()
        url = f"{API_BASE}/{endpoint.lstrip('/')}"

        response = requests.request(method=method, url=url, headers=headers, **kwargs)

        if response.status_code == 401:
            raise ValueError("Authentication expired. Run 'sanebox auth login'")

        response.raise_for_status()

        try:
            return response.json()
        except ValueError:
            return {}

    # -------------------------------------------------------------------------
    # Training
    # -------------------------------------------------------------------------

    def train(self, sender: str, folder: str) -> bool:
        """Train a sender to go to a specific folder."""
        if folder not in self.FOLDERS:
            console.print(f"[yellow]Warning: '{folder}' is not a standard SaneBox folder[/yellow]")

        console.print(f"[cyan]Training {sender} → {folder}...[/cyan]")

        try:
            self._request(
                "POST",
                "/train",
                json={
                    "sender": sender,
                    "folder": folder,
                    "account": self.auth.credentials.active_account,
                },
            )
            console.print(f"[green]✓ Trained {sender} to go to {folder}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Training failed: {e}[/red]")
            return False

    def untrain(self, sender: str) -> bool:
        """Remove training for a sender."""
        console.print(f"[cyan]Removing training for {sender}...[/cyan]")

        try:
            self._request(
                "DELETE",
                f"/train/{sender}",
                json={"account": self.auth.credentials.active_account},
            )
            console.print(f"[green]✓ Removed training for {sender}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Untrain failed: {e}[/red]")
            return False

    # -------------------------------------------------------------------------
    # Blacklist
    # -------------------------------------------------------------------------

    def blacklist_add(self, email: str) -> bool:
        """Add email to blacklist (SaneBlackHole)."""
        return self.train(email, "SaneBlackHole")

    def blacklist_remove(self, email: str) -> bool:
        """Remove email from blacklist."""
        return self.untrain(email)

    def blacklist_list(self) -> list[str]:
        """List all blacklisted emails."""
        try:
            result = self._request(
                "GET",
                "/blacklist",
                params={"account": self.auth.credentials.active_account},
            )
            return result.get("emails", [])
        except Exception as e:
            console.print(f"[red]Failed to get blacklist: {e}[/red]")
            return []

    # -------------------------------------------------------------------------
    # Folders
    # -------------------------------------------------------------------------

    def folders_list(self) -> list[SaneBoxFolder]:
        """List all SaneBox folders with counts."""
        folders = []
        for name in self.FOLDERS:
            try:
                result = self._request(
                    "GET",
                    f"/folder/{name}",
                    params={"account": self.auth.credentials.active_account},
                )
                folders.append(
                    SaneBoxFolder(
                        name=name,
                        count=result.get("count", 0),
                        unread=result.get("unread", 0),
                    )
                )
            except Exception:
                folders.append(SaneBoxFolder(name=name, count=0, unread=0))
        return folders

    def folder_show(self, folder: str, limit: int = 20) -> list[dict]:
        """Show emails in a specific folder."""
        try:
            result = self._request(
                "GET",
                f"/folder/{folder}",
                params={
                    "account": self.auth.credentials.active_account,
                    "limit": limit,
                },
            )
            return result.get("emails", [])
        except Exception as e:
            console.print(f"[red]Failed to get folder contents: {e}[/red]")
            return []

    # -------------------------------------------------------------------------
    # Digest / Stats
    # -------------------------------------------------------------------------

    def digest(self) -> dict:
        """Get today's digest of filtered emails."""
        try:
            result = self._request(
                "GET",
                "/digest",
                params={"account": self.auth.credentials.active_account},
            )
            return result
        except Exception as e:
            console.print(f"[red]Failed to get digest: {e}[/red]")
            return {}

    def stats(self) -> dict:
        """Get SaneBox usage statistics."""
        try:
            result = self._request(
                "GET",
                "/stats",
                params={"account": self.auth.credentials.active_account},
            )
            return result
        except Exception as e:
            console.print(f"[red]Failed to get stats: {e}[/red]")
            return {}

    def accounts_list(self) -> list[str]:
        """List all allowed accounts connected to SaneBox."""
        try:
            result = self._request("GET", "/accounts")
            # Filter to only our allowed accounts
            all_accounts = result.get("accounts", [])
            return [a for a in all_accounts if a in ALLOWED_ACCOUNTS]
        except Exception as e:
            console.print(f"[red]Failed to get accounts: {e}[/red]")
            return []

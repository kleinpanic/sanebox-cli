#!/usr/bin/env python3
"""
SaneBox CLI - Command-line interface for SaneBox email management.

Usage:
    sanebox auth login [--oauth|--session]   # Login to SaneBox
    sanebox auth status                       # Check auth status
    sanebox auth logout                       # Logout

    sanebox accounts list                     # List connected accounts
    sanebox accounts use <email>              # Set active account

    sanebox train <email> --to <folder>       # Train sender to folder
    sanebox untrain <email>                   # Remove training

    sanebox blacklist add <email>             # Add to blacklist
    sanebox blacklist remove <email>          # Remove from blacklist
    sanebox blacklist list                    # List blacklisted emails

    sanebox folders                           # List SaneBox folders
    sanebox folders show <name> [--limit N]   # Show emails in folder

    sanebox digest                            # Today's filtered email digest
    sanebox stats                             # Usage statistics
"""

import click
from rich.console import Console
from rich.table import Table

from sanebox_cli.auth import AuthManager
from sanebox_cli.api import SaneBoxAPI

console = Console()


# Auth group
@click.group()
def auth():
    """Authentication commands."""
    pass


@auth.command()
@click.option("--oauth", is_flag=True, help="Use OAuth (requires client_id from SaneBox)")
@click.option("--session", is_flag=True, help="Paste session cookie from browser DevTools")
@click.option("--client-id", help="OAuth client ID")
@click.option("--email", "-e", help="Email address for direct signin")
@click.option("--password", "-p", default=None, help="Password (prompted if omitted)")
def login(oauth: bool, session: bool, client_id: str, email: str, password: str):
    """Login to SaneBox.

    Three modes:

      sanebox auth login                         # interactive menu

      sanebox auth login -e you@example.com      # direct signin (recommended)

      sanebox auth login --session               # paste cookie from DevTools

      sanebox auth login --oauth                 # OAuth flow (needs client_id)
    """
    auth_mgr = AuthManager()

    if oauth:
        if not client_id:
            client_id = click.prompt("SaneBox OAuth client ID")
        client_secret = click.prompt("Client secret (blank if none)", default="")
        auth_mgr.login_oauth(client_id, client_secret)

    elif email:
        pw = password or click.prompt("Password", hide_input=True)
        auth_mgr.login_signin(email, pw)

    elif session:
        console.print(
            "\n[bold]Get your session cookie:[/bold]\n"
            "1. Open https://www.sanebox.com and log in\n"
            "2. DevTools (F12) → Application → Cookies → www.sanebox.com\n"
            "3. Copy the full cookie string\n"
        )
        session_cookie = click.prompt("Paste cookie")
        auth_mgr.login_session(session_cookie)

    else:
        method = click.prompt(
            "Auth method",
            type=click.Choice(["signin", "session", "oauth"]),
            default="signin",
        )
        if method == "signin":
            em = click.prompt("Email")
            pw = click.prompt("Password", hide_input=True)
            auth_mgr.login_signin(em, pw)
        elif method == "oauth":
            cid = click.prompt("OAuth client ID")
            cs = click.prompt("Client secret (blank if none)", default="")
            auth_mgr.login_oauth(cid, cs)
        else:
            console.print(
                "\n[bold]Get your session cookie:[/bold]\n"
                "1. Open https://www.sanebox.com and log in\n"
                "2. DevTools (F12) → Application → Cookies\n"
                "3. Copy the full cookie string\n"
            )
            session_cookie = click.prompt("Paste cookie")
            auth_mgr.login_session(session_cookie)


@auth.command()
def status():
    """Show authentication status."""
    auth_mgr = AuthManager()
    status = auth_mgr.status()

    if status["authenticated"]:
        console.print("[green]✓ Authenticated[/green]")
        console.print(f"  Method: {status['auth_method']}")
        console.print(f"  Active account: {status.get('active_account', 'None')}")
        if status.get("accounts"):
            console.print(f"  Accounts: {', '.join(status['accounts'])}")
    else:
        console.print(f"[yellow]{status['message']}[/yellow]")


@auth.command()
def logout():
    """Logout from SaneBox."""
    auth_mgr = AuthManager()
    auth_mgr.logout()


# Accounts group
@click.group()
def accounts():
    """Account management commands."""
    pass


@accounts.command("list")
def accounts_list():
    """List connected SaneBox accounts."""
    api = SaneBoxAPI()
    accounts = api.accounts_list()

    if accounts:
        table = Table(title="SaneBox Accounts")
        table.add_column("Email")
        table.add_column("Active")

        for email in accounts:
            is_active = email == api.auth.credentials.active_account
            table.add_row(email, "✓" if is_active else "")

        console.print(table)
    else:
        console.print("[yellow]No accounts found[/yellow]")


@accounts.command("use")
@click.argument("email")
def accounts_use(email: str):
    """Set active account."""
    auth_mgr = AuthManager()
    auth_mgr.set_active_account(email)


# Train command
@click.command()
@click.argument("sender")
@click.option(
    "--to", "folder", required=True, help="Target folder (SaneLater, SaneBlackHole, etc.)"
)
def train(sender: str, folder: str):
    """Train a sender to go to a specific folder."""
    api = SaneBoxAPI()
    api.train(sender, folder)


@click.command()
@click.argument("sender")
def untrain(sender: str):
    """Remove training for a sender."""
    api = SaneBoxAPI()
    api.untrain(sender)


# Blacklist group
@click.group()
def blacklist():
    """Blacklist management commands."""
    pass


@blacklist.command("add")
@click.argument("email")
def blacklist_add(email: str):
    """Add email to blacklist (SaneBlackHole)."""
    api = SaneBoxAPI()
    api.blacklist_add(email)


@blacklist.command("remove")
@click.argument("email")
def blacklist_remove(email: str):
    """Remove email from blacklist."""
    api = SaneBoxAPI()
    api.blacklist_remove(email)


@blacklist.command("list")
def blacklist_list():
    """List blacklisted emails."""
    api = SaneBoxAPI()
    emails = api.blacklist_list()

    if emails:
        table = Table(title="Blacklisted Emails")
        table.add_column("Email")
        for email in emails:
            table.add_row(email)
        console.print(table)
    else:
        console.print("[yellow]No blacklisted emails[/yellow]")


# Folders command
@click.command()
@click.argument("folder_name", required=False)
@click.option("--limit", "-l", default=20, help="Number of emails to show")
def folders(folder_name: str, limit: int):
    """List SaneBox folders or show emails in a folder."""
    api = SaneBoxAPI()

    if folder_name:
        # Show emails in specific folder
        emails = api.folder_show(folder_name, limit=limit)
        if emails:
            table = Table(title=f"Emails in {folder_name}")
            table.add_column("From")
            table.add_column("Subject")
            table.add_column("Date")

            for email in emails[:limit]:
                table.add_row(
                    email.get("from", ""), email.get("subject", "")[:50], email.get("date", "")
                )
            console.print(table)
        else:
            console.print(f"[yellow]No emails in {folder_name}[/yellow]")
    else:
        # List all folders
        folders = api.folders_list()

        table = Table(title="SaneBox Folders")
        table.add_column("Folder")
        table.add_column("Total", justify="right")
        table.add_column("Unread", justify="right")

        for folder in folders:
            table.add_row(folder.name, str(folder.count), str(folder.unread))

        console.print(table)


# Digest command
@click.command()
def digest():
    """Show today's filtered email digest."""
    api = SaneBoxAPI()
    result = api.digest()

    if result:
        console.print("[bold]Today's Digest[/bold]\n")
        for folder, emails in result.items():
            if emails:
                console.print(f"[cyan]{folder}[/cyan]: {len(emails)} emails")
    else:
        console.print("[yellow]No digest available[/yellow]")


# Stats command
@click.command()
def stats():
    """Show SaneBox usage statistics."""
    api = SaneBoxAPI()
    result = api.stats()

    if result:
        table = Table(title="SaneBox Statistics")
        table.add_column("Metric")
        table.add_column("Value")

        for key, value in result.items():
            table.add_row(key, str(value))

        console.print(table)
    else:
        console.print("[yellow]No stats available[/yellow]")


# Main CLI group
@click.group()
def cli():
    """SaneBox CLI - Manage your SaneBox email sorting from the command line."""
    pass


# Add all commands
cli.add_command(auth)
cli.add_command(accounts)
cli.add_command(train)
cli.add_command(untrain)
cli.add_command(blacklist)
cli.add_command(folders)
cli.add_command(digest)
cli.add_command(stats)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()

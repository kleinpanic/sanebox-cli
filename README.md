# SaneBox CLI

Command-line interface for SaneBox email management. Train senders, manage blacklist, view digests.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install sanebox-cli
```

## Quick Start

```bash
# Login (supports OAuth or session cookie)
sanebox auth login

# Set active account (if you have multiple)
sanebox accounts use you@example.com

# Train a sender
sanebox train newsletter@spam.com --to SaneLater
sanebox train spam@evil.com --to SaneBlackHole

# View folders
sanebox folders
sanebox folders show SaneLater --limit 10

# Blacklist management
sanebox blacklist add spam@example.com
sanebox blacklist list

# View digest and stats
sanebox digest
sanebox stats
```

## Authentication

### Option 1: OAuth (Recommended)

```bash
sanebox auth login --oauth --client-id YOUR_CLIENT_ID
```

Requires a `client_id` from SaneBox (contact support).

### Option 2: Session Cookie (Fallback)

```bash
sanebox auth login --session
```

1. Open https://www.sanebox.com in your browser
2. Login to your account
3. Open DevTools (F12) → Application → Cookies
4. Copy the `_session` cookie value
5. Paste when prompted

## Commands

### Auth
- `sanebox auth login [--oauth|--session]` - Login to SaneBox
- `sanebox auth status` - Check authentication status
- `sanebox auth logout` - Logout

### Accounts
- `sanebox accounts list` - List connected accounts
- `sanebox accounts use <email>` - Set active account

### Training
- `sanebox train <email> --to <folder>` - Train sender to folder
- `sanebox untrain <email>` - Remove training

### Folders
- `sanebox folders` - List all SaneBox folders
- `sanebox folders show <name>` - Show emails in folder

### Blacklist
- `sanebox blacklist add <email>` - Add to blacklist
- `sanebox blacklist remove <email>` - Remove from blacklist
- `sanebox blacklist list` - List blacklisted emails

### Info
- `sanebox digest` - Today's filtered email digest
- `sanebox stats` - Usage statistics

## SaneBox Folders

| Folder | Purpose |
|--------|---------|
| `SaneLater` | Non-urgent emails |
| `SaneNews` | Newsletters |
| `SaneBlackHole` | Auto-delete after 7 days |
| `SaneNoReplies` | Sent items awaiting reply |
| `SaneCC` | CC'd emails |
| `SaneBulk` | Bulk mail |
| `SaneNotSpam` | Rescued from spam |

## Development

```bash
git clone https://github.com/kleinpanic/sanebox-cli.git
cd sanebox-cli
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## License

MIT License

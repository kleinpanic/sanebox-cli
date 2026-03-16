"""
SaneBox CLI - Command-line interface for SaneBox email management.

Supports dual authentication:
1. OAuth API (official - requires client_id from SaneBox)
2. Session auth (extract session from browser for direct API calls)
"""

__version__ = "0.1.0"

from sanebox_cli.api import SaneBoxAPI
from sanebox_cli.auth import AuthManager

__all__ = ["SaneBoxAPI", "AuthManager"]

#!/usr/bin/env python3
"""
One-time OAuth setup for the poker tournament scripts.

Re-authorizes your token to add the `script.projects` scope on top of
`spreadsheets` and `drive` — needed so the create_sheet*.py scripts can
auto-install the blinds timer Apps Script instead of you copy-pasting it.

Usage:
    pip install google-auth-oauthlib
    python3 setup_auth.py

Opens a browser. Sign in, grant the permissions, token is saved at the same
path as before (overwrites). Re-run any time the scope list changes.
"""

import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

DEFAULT_TOKEN_PATH = "/Users/sophie.arborbot/.openclaw/workspace/arborfam-hub-token.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects",
]


def main() -> None:
    token_path = os.environ.get("POKER_TOKEN_PATH", DEFAULT_TOKEN_PATH)

    if not os.path.exists(token_path):
        print(f"Error: existing token not found at {token_path}")
        print()
        print("This script needs the client_id/client_secret from an existing OAuth")
        print("token to bootstrap re-authorization. Set POKER_TOKEN_PATH to point at")
        print("your existing token, or place it at the default path above.")
        sys.exit(1)

    with open(token_path) as f:
        existing = json.load(f)

    client_id = existing.get("client_id")
    client_secret = existing.get("client_secret")
    if not (client_id and client_secret):
        print("Error: existing token doesn't carry client_id/client_secret.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    print("Opening browser for authorization...")
    print(f"Requesting scopes:")
    for s in SCOPES:
        print(f"  - {s}")
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        "universe_domain": existing.get("universe_domain", "googleapis.com"),
        "account": existing.get("account", ""),
        "expiry": creds.expiry.isoformat() + "Z" if creds.expiry else None,
    }

    with open(token_path, "w") as f:
        json.dump(token_data, f, indent=2)

    print()
    print(f"✓ Token saved to {token_path}")
    print(f"  Scopes granted: {', '.join(SCOPES)}")


if __name__ == "__main__":
    main()

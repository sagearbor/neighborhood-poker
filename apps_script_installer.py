"""Apps Script auto-installer for the poker blinds timer.

Programmatically creates a bound Apps Script project on a given spreadsheet
and uploads `apps-script/blinds_timer.gs` + `apps-script/timer_dialog.html`,
removing the need to copy-paste them into the Apps Script editor by hand.

Requires:
  - The script.projects OAuth scope (run setup_auth.py once to add it)
  - The Apps Script API enabled in the Google Cloud project that issued the
    token: https://console.cloud.google.com/apis/library/script.googleapis.com
"""

import json
import os

from googleapiclient.discovery import build

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
APPS_SCRIPT_DIR = os.path.join(REPO_ROOT, "apps-script")

# Bound-script manifest. spreadsheets.currentonly limits the script to the
# parent spreadsheet; script.container.ui is needed for the modal timer dialog.
APPSCRIPT_MANIFEST = {
    "timeZone": "America/New_York",
    "dependencies": {},
    "exceptionLogging": "STACKDRIVER",
    "runtimeVersion": "V8",
    "oauthScopes": [
        "https://www.googleapis.com/auth/spreadsheets.currentonly",
        "https://www.googleapis.com/auth/script.container.ui",
    ],
}


def install_timer(creds, spreadsheet_id: str, title: str = "Poker Blinds Timer") -> str:
    """Create a bound Apps Script project on the spreadsheet and upload the
    timer files. Returns the script editor URL. Raises on failure."""
    script_service = build("script", "v1", credentials=creds)

    with open(os.path.join(APPS_SCRIPT_DIR, "blinds_timer.gs")) as f:
        code_source = f.read()
    with open(os.path.join(APPS_SCRIPT_DIR, "timer_dialog.html")) as f:
        html_source = f.read()

    project = script_service.projects().create(
        body={"title": title, "parentId": spreadsheet_id}
    ).execute()
    script_id = project["scriptId"]

    script_service.projects().updateContent(
        scriptId=script_id,
        body={
            "files": [
                {
                    "name": "appsscript",
                    "type": "JSON",
                    "source": json.dumps(APPSCRIPT_MANIFEST, indent=2),
                },
                {
                    "name": "Code",
                    "type": "SERVER_JS",
                    "source": code_source,
                },
                {
                    "name": "TimerDialog",
                    "type": "HTML",
                    "source": html_source,
                },
            ]
        },
    ).execute()

    return f"https://script.google.com/d/{script_id}/edit"


def try_install_timer(creds, spreadsheet_id: str) -> bool:
    """Install the timer, printing friendly status. Returns True on success,
    False on failure. Doesn't raise — falls back to a manual-install message."""
    try:
        url = install_timer(creds, spreadsheet_id)
    except Exception as e:
        msg = str(e)
        print(f"⚠ Couldn't auto-install Apps Script: {msg[:300]}")
        if "script.projects" in msg or "insufficient" in msg.lower():
            print("  → Run `python3 setup_auth.py` to add the required scope, then re-run.")
        elif "API has not been used" in msg or "disabled" in msg.lower() or "SERVICE_DISABLED" in msg:
            print("  → Enable the Apps Script API:")
            print("    https://console.cloud.google.com/apis/library/script.googleapis.com")
        print("  Falling back to manual install — see BLINDS_TIMER_SETUP.md.")
        return False

    print(f"✓ Timer Apps Script installed: {url}")
    print("  The 🃏 Poker Timer menu will appear when you open the sheet.")
    print("  (You'll be prompted to authorize the script the first time you click Start Timer.)")
    return True

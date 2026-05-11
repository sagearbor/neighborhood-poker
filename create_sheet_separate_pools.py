#!/usr/bin/env python3
"""
Create the Poker Tournament Manager — Separate Prize Pools Edition Google Sheet.

Variant of create_sheet.py where Fish and Whale prize pools are COMPLETELY
separate. Fish buy-ins fund the Fish Pot and pay only Fish placements; Whale
buy-ins fund the Whale Pot and pay only Whale placements. The $10 headhunter
bounty chip (configurable in Settings!B4) is the only cross-track incentive —
whales still want to bust short-stacked fish for the bounty.

Differences vs. create_sheet.py:
  - No Main Pot / Side Pot. Each player's buy-in feeds ONLY their track pot.
  - Each track has its own payout table that scales with that track's player
    count, using the same payout tier table from Settings applied independently.
  - Settings adds a "Suggested Bounty" calc cell (= 25% of base buy-in, rounded);
    actual bounty in B4 remains user-editable.
  - Payout tier table adds a 1-player tier (1 place at 100%) so very small
    tracks still pay out cleanly.
  - Payout-lookup formulas are wrapped in AND() so IFS() actually returns a
    percentage rather than TRUE/FALSE at boundary cases.
  - The Blinds Timer tab ships with the full schedule inline — no separate
    update_blinds.py step required.

Usage:
    pip install google-auth google-auth-oauthlib google-api-python-client
    python3 create_sheet_separate_pools.py [--credentials path/to/credentials.json]
"""

import argparse
import json
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_TITLE = "Poker Tournament Manager — Separate Prize Pools Edition"

# Default path matches update_blinds.py — a user OAuth token JSON.
DEFAULT_CREDENTIALS = "/Users/sophie.arborbot/.openclaw/workspace/arborfam-hub-token.json"

PLAYER_ROWS = 30
FIRST_PLAYER_ROW = 2
LAST_PLAYER_ROW = FIRST_PLAYER_ROW + PLAYER_ROWS - 1  # 31

SID_SETTINGS = 0
SID_REGISTRATION = 1
SID_DASHBOARD = 2
SID_LIVE = 3
SID_INSTRUCTIONS = 4
SID_BLINDS = 5

# Colors
WHITE = {"red": 1, "green": 1, "blue": 1}
LIGHT_GRAY = {"red": 0.93, "green": 0.93, "blue": 0.93}
LIGHT_BLUE = {"red": 0.85, "green": 0.92, "blue": 1.0}
LIGHT_GOLD = {"red": 1.0, "green": 0.95, "blue": 0.8}
CHART_BLUE = {"red": 0.26, "green": 0.52, "blue": 0.96}
CHART_GOLD = {"red": 0.98, "green": 0.74, "blue": 0.18}

# Blinds Timer colors
DARK_HEADER = {"red": 0.15, "green": 0.15, "blue": 0.3}
ORANGE_BREAK = {"red": 1.0, "green": 0.8, "blue": 0.4}
LIGHT_ROW = {"red": 0.95, "green": 0.95, "blue": 1.0}
SETTINGS_BG = {"red": 0.93, "green": 0.96, "blue": 1.0}

# Payout tier table position in Settings (1-indexed sheet rows)
TIER_FIRST_ROW = 17
TIER_LAST_ROW = 22  # 6 tiers (rows 17-22)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def authorize(credentials_path: str):
    """Load a user OAuth token JSON (matches update_blinds.py auth flow)."""
    with open(credentials_path) as f:
        token_data = json.load(f)
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes", SCOPES),
    )
    sheets = build("sheets", "v4", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return sheets, drive


def col_letter(index: int) -> str:
    """0-based column index → letter (0='A', 25='Z', 26='AA')."""
    result = ""
    while True:
        result = chr(index % 26 + ord("A")) + result
        index = index // 26 - 1
        if index < 0:
            break
    return result


def bold_fmt():
    return {"textFormat": {"bold": True}}


def currency_fmt():
    return {"numberFormat": {"type": "NUMBER", "pattern": '$#,##0.00'}}


# ---------------------------------------------------------------------------
# Settings tab
# ---------------------------------------------------------------------------

def build_settings_data():
    """Settings tab layout — header on row 16, tier rows 17-22 (1-indexed)."""
    rows = []

    # Sheet row 1: title
    rows.append(["⚙️ SETTINGS"])

    # Sheet rows 2-7: 6 inputs
    inputs = [
        ("Base Buy-in ($)", 40, "Standard entry for Low (Fish) track"),
        ("High Roller Multiplier", 4, "High (Whale) buy-in = base × this"),
        ("Bounty ($)", 10, "Headhunter chip per knockout — edit freely"),
        ("Top-Off Multiplier", 0.5, "Break top-off as fraction of buy-in"),
        ("Max Rebuys", 2, "Max rebuys per player"),
        ("Rake %", 0, "House rake (0 for home games)"),
    ]
    for label, val, note in inputs:
        rows.append([label, val, note])

    # Sheet row 8: blank
    rows.append([])

    # Sheet rows 9-15: 7 calculated values
    calcs = [
        ("Fish Buy-in", "=B2"),
        ("Whale Buy-in", "=B2*B3"),
        ("Suggested Bounty", "=ROUND(B2*0.25,0)"),
        ("Low Top-Off Cost", "=B2*B5"),
        ("High Top-Off Cost", "=B2*B3*B5"),
        ("Low Total Entry", "=B2+B4"),
        ("High Total Entry", "=(B2*B3)+B4"),
    ]
    for label, formula in calcs:
        rows.append([label, "→", formula])

    # Sheet row 16: payout header
    rows.append(["Min Players", "Max Players", "Places Paid",
                 "1st%", "2nd%", "3rd%", "4th%", "5th%"])

    # Sheet rows 17-22: 6 payout tiers (new 1-player tier on top)
    tiers = [
        [1, 1, 1, 100, 0, 0, 0, 0],
        [2, 4, 1, 100, 0, 0, 0, 0],
        [5, 8, 2, 65, 35, 0, 0, 0],
        [9, 15, 3, 50, 30, 20, 0, 0],
        [16, 25, 4, 45, 27, 17, 11, 0],
        [26, 999, 5, 40, 25, 16, 11, 8],
    ]
    for tier in tiers:
        rows.append(tier)

    return rows


# ---------------------------------------------------------------------------
# Registration tab
# ---------------------------------------------------------------------------

def build_registration_headers():
    return [["Player Name", "Track", "Buy-in Paid?", "Rebuy Count",
             "Top-Off?", "Total Cash", "Fish Pot", "Whale Pot", "Bounty"]]


def reg_formulas(r: int) -> list:
    """Formulas for columns F-I at 1-based row r."""
    # F: Total Cash collected from this player (entry+rebuys with bounty,
    # plus top-off without bounty).
    f_total = (
        f'=IF(C{r},IF(B{r}="High",(Settings!$B$2*Settings!$B$3)+Settings!$B$4,'
        f"Settings!$B$2+Settings!$B$4),0)"
        f"+D{r}*IF(B{r}=\"High\",(Settings!$B$2*Settings!$B$3)+Settings!$B$4,"
        f"Settings!$B$2+Settings!$B$4)"
        f"+IF(E{r},IF(B{r}=\"High\",Settings!$B$2*Settings!$B$3*Settings!$B$5,"
        f"Settings!$B$2*Settings!$B$5),0)"
    )

    # G: Fish Pot — full Fish buy-in / rebuy / top-off contribution
    g_fish = (
        f'=IF(B{r}="Low",'
        f"IF(C{r},Settings!$B$2,0)"
        f"+D{r}*Settings!$B$2"
        f"+IF(E{r},Settings!$B$2*Settings!$B$5,0)"
        f",0)"
    )

    # H: Whale Pot — full Whale buy-in / rebuy / top-off contribution
    h_whale = (
        f'=IF(B{r}="High",'
        f"IF(C{r},Settings!$B$2*Settings!$B$3,0)"
        f"+D{r}*Settings!$B$2*Settings!$B$3"
        f"+IF(E{r},Settings!$B$2*Settings!$B$3*Settings!$B$5,0)"
        f",0)"
    )

    # I: Bounty (any track)
    i_bounty = (
        f"=IF(C{r},Settings!$B$4,0)"
        f"+D{r}*Settings!$B$4"
    )

    return [f_total, g_fish, h_whale, i_bounty]


def build_registration_formulas():
    rows = []
    for r in range(FIRST_PLAYER_ROW, LAST_PLAYER_ROW + 1):
        formulas = reg_formulas(r)
        rows.append(["", "", False, 0, False] + formulas)
    return rows


# ---------------------------------------------------------------------------
# Dashboard tab
# ---------------------------------------------------------------------------

def _tier_lookup_formula(count_cell: str, pct_col_letter: str) -> str:
    """Build IFS lookup against the 6-row tier table at Settings rows 17-22.

    Each tier condition is wrapped in AND() so IFS returns the percentage
    value, not a boolean.
    """
    pairs = []
    for tier_row in range(TIER_LAST_ROW, TIER_FIRST_ROW - 1, -1):
        cond = (
            f"AND({count_cell}>=Settings!A{tier_row},"
            f"{count_cell}<=Settings!B{tier_row})"
        )
        val = f"Settings!{pct_col_letter}{tier_row}"
        pairs.append(f"{cond},{val}")
    return f"=IFERROR(IFS({','.join(pairs)}),0)"


def build_dashboard_data():
    """Dashboard layout (Python indices = sheet rows minus 1):

      0  📊 DASHBOARD
      1  (blank)
      2  Total Players       | B3
      3  Fish (Low) Count    | B4
      4  Whale (High) Count  | B5
      5  (blank)
      6  Total Cash in Box   | B7
      7  Bounty Pool         | B8
      8  Fish Pot Total      | B9
      9  Whale Pot Total     | B10
      10 Rake Amount         | B11
      11 (blank)
      12 FISH PAYOUTS header + chart helper header
      13-17  fish places 1..5 (cols A-D) + chart helper E-G
      18 (blank)
      19 WHALE PAYOUTS header
      20-24  whale places 1..5
    """
    lr = LAST_PLAYER_ROW
    rows = []

    rows.append(["📊 DASHBOARD"])
    rows.append([])

    rows.append(["Total Players",
                 f'=COUNTIF(Registration!B2:B{lr},"Low")'
                 f'+COUNTIF(Registration!B2:B{lr},"High")'])
    rows.append(["Fish (Low) Count", f'=COUNTIF(Registration!B2:B{lr},"Low")'])
    rows.append(["Whale (High) Count", f'=COUNTIF(Registration!B2:B{lr},"High")'])

    rows.append([])

    rows.append(["Total Cash in Box", f"=SUM(Registration!F2:F{lr})"])
    rows.append(["Bounty Pool", f"=SUM(Registration!I2:I{lr})"])
    rows.append(["Fish Pot Total",
                 f"=SUM(Registration!G2:G{lr})*(1-Settings!$B$7/100)"])
    rows.append(["Whale Pot Total",
                 f"=SUM(Registration!H2:H{lr})*(1-Settings!$B$7/100)"])
    rows.append(["Rake Amount",
                 f"=(SUM(Registration!G2:G{lr})+SUM(Registration!H2:H{lr}))"
                 f"*Settings!$B$7/100"])

    rows.append([])

    # FISH PAYOUTS header (with chart helper cols E-G)
    rows.append(["FISH PAYOUTS", "Place", "Pct%", "Amount ($)",
                 "Place", "🐟 Fish ($)", "🐋 Whales ($)"])

    places = ["1st", "2nd", "3rd", "4th", "5th"]
    fish_first_row = 14   # 1-indexed sheet row of first fish payout line
    whale_first_row = 21  # 1-indexed sheet row of first whale payout line

    for i, place in enumerate(places):
        pct_col = col_letter(3 + i)  # D=1st%, E=2nd%, F=3rd%, G=4th%, H=5th%
        pct_formula = _tier_lookup_formula("$B$4", pct_col)  # B4 = fish count
        amt_formula = f"=FLOOR($B$9*C{fish_first_row + i}/100,5)"  # B9 = fish pot total
        chart_place = place
        fish_chart = f"=D{fish_first_row + i}"
        whale_chart = f"=D{whale_first_row + i}"
        rows.append(["", place, pct_formula, amt_formula,
                     chart_place, fish_chart, whale_chart])

    rows.append([])  # blank between tables

    rows.append(["WHALE PAYOUTS", "Place", "Pct%", "Amount ($)"])

    for i, place in enumerate(places):
        pct_col = col_letter(3 + i)
        pct_formula = _tier_lookup_formula("$B$5", pct_col)  # B5 = whale count
        amt_formula = f"=FLOOR($B$10*C{whale_first_row + i}/100,5)"  # B10 = whale pot total
        rows.append(["", place, pct_formula, amt_formula])

    return rows


# ---------------------------------------------------------------------------
# Instructions tab
# ---------------------------------------------------------------------------

def build_instructions_data():
    lines = [
        ["📖 INSTRUCTIONS — SEPARATE PRIZE POOLS EDITION"],
        [],
        ["HOW THIS IS DIFFERENT FROM THE CONCURRENT FLIGHT EDITION"],
        ["Fish and Whales play at the same physical table with the same chip stack,"],
        ["but their PRIZE POOLS ARE COMPLETELY SEPARATE."],
        ["  • Fish $40 buy-in → Fish Pot only. Whales cannot win it."],
        ["  • Whale $160 buy-in → Whale Pot only. Fish cannot win it."],
        ["  • Each track has its own payout table that scales independently"],
        ["    with that track's player count."],
        ["The Bounty (headhunter) chip is the only cross-track incentive: $10 (or"],
        ["whatever you set in Settings!B4) per knockout regardless of victim's track."],
        ["So whales still want to bust short-stacked fish."],
        [],
        ["HOW TO RUN TOURNAMENT NIGHT"],
        ["1. Open the Registration tab before players arrive."],
        ["2. Add each player's name in column A."],
        ['3. Select their track — Low (Fish) or High (Whale) — from the dropdown.'],
        ['4. Check "Buy-in Paid?" when they hand you cash.'],
        ["5. Rebuys: increment Rebuy Count (max 2) if a player buys back in."],
        ["6. Top-offs: check the Top-Off box during the break if they add chips."],
        ["7. Watch the Dashboard tab for live totals — both pots + bounty pool."],
        ["8. Pay out using the Dashboard payout tables:"],
        ["   - Fish Pot: top N fish by bust-out order (scales with fish count)"],
        ["   - Whale Pot: top N whales by bust-out order (scales with whale count)"],
        ["   - Bounty: $10 per knockout from the bounty pool (any track)"],
        [],
        ["HOW PLACES PAID SCALES (same tier table applied to each track separately)"],
        ["  1 player:    1 place paid (100%)"],
        ["  2-4:         1 place (100%)"],
        ["  5-8:         2 places (65/35)"],
        ["  9-15:        3 places (50/30/20)"],
        ["  16-25:       4 places (45/27/17/11)"],
        ["  26+:         5 places (40/25/16/11/8)"],
        [],
        ["HOW TO START A NEW QUARTER"],
        ['1. Right-click the Registration tab → Duplicate.'],
        ['2. Rename the duplicate (e.g., "Registration Q3 2026").'],
        ["3. Clear all player data from the active Registration tab."],
        ["4. The Dashboard automatically recalculates."],
        [],
        ["SETTINGS REFERENCE"],
        ["Base Buy-in (B2): standard entry for Fish track (default $40)."],
        ["High Roller Multiplier (B3): Whale buy-in = base × this (default 4× = $160)."],
        ["Bounty (B4): per-knockout headhunter chip (default $10) — edit freely."],
        ["  See the 'Suggested Bounty' calc cell for a 25%-of-buy-in starting point."],
        ["Top-Off Multiplier (B5): break top-off as fraction of buy-in (default 0.5×)."],
        ["Max Rebuys (B6): maximum rebuys allowed per player (default 2)."],
        ["Rake % (B7): house rake percentage (default 0% for home games)."],
        [],
        ["BLINDS TIMER"],
        ["The same Apps Script timer works on this sheet — install it via"],
        ["Extensions → Apps Script, following BLINDS_TIMER_SETUP.md."],
        ["The full schedule is already populated in the ⏱ Blinds Timer tab."],
        [],
        ["SOURCE CODE & UPDATES"],
        ["https://github.com/sagearbor/neighborhood-poker"],
    ]
    return lines


# ---------------------------------------------------------------------------
# Blinds Timer tab (full schedule inline — mirrors update_blinds.py output)
# ---------------------------------------------------------------------------

def build_blinds_data():
    rows = []

    # Rows 0-3 (sheet 1-4): settings block
    rows.append(["⏱ BLINDS TIMER", "", "", "", "", ""])
    rows.append(["Starting Stack:", "10,000", "", "Ante starts at level:", 5, ""])
    rows.append(["Level duration default:", "20 min", "", "", "", ""])
    rows.append(["💡 Highlight the current row manually as you progress",
                 "", "", "", "", ""])

    # Row 4 (sheet 5): blank
    rows.append([])

    # Row 5 (sheet 6): header
    rows.append(["Level", "Small Blind", "Big Blind", "Ante",
                 "Duration (min)", "Total Time Elapsed"])

    # Rows 6+ (sheet 7+): schedule (apps-script reads from sheet row 7 onward)
    schedule = [
        ("1", 25, 50, 20, False, ""),
        ("2", 50, 100, 20, False, ""),
        ("3", 75, 150, 20, False, ""),
        ("4", 100, 200, 20, False, ""),
        ("BREAK", None, None, 10, True, "BREAK — Top-off allowed"),
        ("5", 150, 300, 20, False, ""),
        ("6", 200, 400, 20, False, ""),
        ("7", 300, 600, 20, False, ""),
        ("8", 400, 800, 20, False, ""),
        ("BREAK", None, None, 10, True, "BREAK"),
        ("9", 500, 1000, 15, False, ""),
        ("10", 750, 1500, 15, False, ""),
        ("11", 1000, 2000, 15, False, ""),
        ("12", 1500, 3000, 15, False, ""),
        ("13", 2000, 4000, 15, False, ""),
    ]

    data_start_row = 7  # 1-indexed sheet row of first data row
    for i, (level, sb, bb, duration, is_break, note) in enumerate(schedule):
        row_1idx = data_start_row + i
        elapsed = f"=E{row_1idx}" if i == 0 else f"=F{row_1idx - 1}+E{row_1idx}"
        if is_break:
            rows.append([note, "", "", "", duration, elapsed])
        else:
            level_num = int(level)
            ante_formula = f'=IF({level_num}>=$E$2,"Yes","")'
            rows.append([f"Level {level}", sb, bb, ante_formula, duration, elapsed])

    return rows


# ---------------------------------------------------------------------------
# Formatting & validation
# ---------------------------------------------------------------------------

def make_format_requests():
    requests = []

    # --- Settings tab ---
    # Title bold (row 1)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Calculated cells gray bg (rows 9-15 in sheet = Python 8-14)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 8, "endRowIndex": 15,
                      "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"backgroundColor": LIGHT_GRAY}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Payout header bold (row 16 in sheet = Python 15)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 15, "endRowIndex": 16},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # --- Registration tab ---
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_REGISTRATION, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": SID_REGISTRATION,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # Currency on F-I
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 5, "endColumnIndex": 9},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Track dropdown
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "Low"},
                        {"userEnteredValue": "High"},
                    ],
                },
                "showCustomUi": True,
                "strict": True,
            },
        }
    })

    # Buy-in checkbox
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 2, "endColumnIndex": 3},
            "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
        }
    })

    # Rebuy 0-2
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 3, "endColumnIndex": 4},
            "rule": {
                "condition": {
                    "type": "NUMBER_BETWEEN",
                    "values": [
                        {"userEnteredValue": "0"},
                        {"userEnteredValue": "2"},
                    ],
                },
                "showCustomUi": True,
                "strict": True,
            },
        }
    })

    # Top-off checkbox
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 4, "endColumnIndex": 5},
            "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
        }
    })

    # CF: Low → blue, High → gold
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": SID_REGISTRATION,
                            "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                            "startColumnIndex": 0, "endColumnIndex": 9}],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": '=$B2="Low"'}],
                    },
                    "format": {"backgroundColor": LIGHT_BLUE},
                },
            },
            "index": 0,
        }
    })
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": SID_REGISTRATION,
                            "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                            "startColumnIndex": 0, "endColumnIndex": 9}],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": '=$B2="High"'}],
                    },
                    "format": {"backgroundColor": LIGHT_GOLD},
                },
            },
            "index": 1,
        }
    })

    # --- Dashboard tab ---
    # Title bold
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Summary labels bold (col A, Python rows 2-10 = sheet rows 3-11)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                      "startRowIndex": 2, "endRowIndex": 11,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Currency on summary B (Python rows 6-10 = money rows)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                      "startRowIndex": 6, "endRowIndex": 11,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Payout table headers bold (Python rows 12 and 19)
    for row_idx in [12, 19]:
        requests.append({
            "repeatCell": {
                "range": {"sheetId": SID_DASHBOARD,
                          "startRowIndex": row_idx, "endRowIndex": row_idx + 1},
                "cell": {"userEnteredFormat": bold_fmt()},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        })

    # Currency on payout amount col D (Python fish rows 13-17, whale rows 20-24)
    for start, end in [(13, 18), (20, 25)]:
        requests.append({
            "repeatCell": {
                "range": {"sheetId": SID_DASHBOARD,
                          "startRowIndex": start, "endRowIndex": end,
                          "startColumnIndex": 3, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": currency_fmt()},
                "fields": "userEnteredFormat.numberFormat",
            }
        })

    # Currency on chart helper F-G (Python rows 13-17)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                      "startRowIndex": 13, "endRowIndex": 18,
                      "startColumnIndex": 5, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # --- Live Payouts: hide gridlines ---
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": SID_LIVE,
                "gridProperties": {"hideGridlines": True},
            },
            "fields": "gridProperties.hideGridlines",
        }
    })

    # --- Instructions header bold ---
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_INSTRUCTIONS, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # --- Blinds Timer formatting ---
    col_widths = [(0, 200), (1, 120), (2, 120), (3, 80), (4, 140), (5, 180)]
    for col_idx, width in col_widths:
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": SID_BLINDS,
                    "dimension": "COLUMNS",
                    "startIndex": col_idx,
                    "endIndex": col_idx + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })

    # 14pt minimum across timer tab
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 0, "endRowIndex": 22},
            "cell": {"userEnteredFormat": {"textFormat": {"fontSize": 14}}},
            "fields": "userEnteredFormat.textFormat.fontSize",
        }
    })

    # Title (row 0): bold 18pt
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 18}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # Settings rows (1-2): bold + light bg
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 1, "endRowIndex": 3,
                      "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {
                "backgroundColor": SETTINGS_BG,
                "textFormat": {"bold": True, "fontSize": 14},
            }},
            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat",
        }
    })

    # Note row (3): italic
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 3, "endRowIndex": 4,
                      "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"textFormat": {"italic": True, "fontSize": 12}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # Header (row 5): dark bg, white bold, centered
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 5, "endRowIndex": 6,
                      "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {
                "backgroundColor": DARK_HEADER,
                "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": WHITE},
                "horizontalAlignment": "CENTER",
            }},
            "fields": ("userEnteredFormat.backgroundColor,"
                       "userEnteredFormat.textFormat,"
                       "userEnteredFormat.horizontalAlignment"),
        }
    })

    # Data rows: alternating shading + break highlights
    break_indices = [4, 9]
    data_start = 6
    for i in range(15):
        row_idx = data_start + i
        if i in break_indices:
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": SID_BLINDS,
                              "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                              "startColumnIndex": 0, "endColumnIndex": 6},
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": ORANGE_BREAK,
                        "textFormat": {"bold": True, "fontSize": 14},
                        "horizontalAlignment": "CENTER",
                    }},
                    "fields": ("userEnteredFormat.backgroundColor,"
                               "userEnteredFormat.textFormat,"
                               "userEnteredFormat.horizontalAlignment"),
                }
            })
        else:
            non_break_count = i - sum(1 for b in break_indices if b < i)
            bg = LIGHT_ROW if non_break_count % 2 == 0 else WHITE
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": SID_BLINDS,
                              "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                              "startColumnIndex": 0, "endColumnIndex": 6},
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": bg,
                        "horizontalAlignment": "CENTER",
                    }},
                    "fields": ("userEnteredFormat.backgroundColor,"
                               "userEnteredFormat.horizontalAlignment"),
                }
            })

    # Left-align level column for data rows
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS,
                      "startRowIndex": data_start, "endRowIndex": data_start + 15,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT"}},
            "fields": "userEnteredFormat.horizontalAlignment",
        }
    })

    # Number format for SB/BB columns
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS,
                      "startRowIndex": data_start, "endRowIndex": data_start + 15,
                      "startColumnIndex": 1, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Freeze first 6 rows of timer tab
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": SID_BLINDS,
                "gridProperties": {"frozenRowCount": 6},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    return requests


def make_chart_request():
    """Chart on Live Payouts comparing Fish vs Whale payouts by place.

    Pulls from Dashboard chart-helper cols E-G across Python rows 12-17
    (sheet rows 13-18 — header + 5 places).
    """
    return {
        "addChart": {
            "chart": {
                "position": {
                    "overlayPosition": {
                        "anchorCell": {"sheetId": SID_LIVE, "rowIndex": 1, "columnIndex": 0},
                        "widthPixels": 900,
                        "heightPixels": 550,
                    }
                },
                "spec": {
                    "title": "🏆 Tonight's Prize Pools — Fish vs Whales (Separate)",
                    "basicChart": {
                        "chartType": "COLUMN",
                        "legendPosition": "BOTTOM_LEGEND",
                        "headerCount": 1,
                        "domains": [{
                            "domain": {
                                "sourceRange": {
                                    "sources": [{
                                        "sheetId": SID_DASHBOARD,
                                        "startRowIndex": 12,
                                        "endRowIndex": 18,
                                        "startColumnIndex": 4,
                                        "endColumnIndex": 5,
                                    }]
                                }
                            }
                        }],
                        "series": [
                            {
                                "series": {
                                    "sourceRange": {
                                        "sources": [{
                                            "sheetId": SID_DASHBOARD,
                                            "startRowIndex": 12,
                                            "endRowIndex": 18,
                                            "startColumnIndex": 5,
                                            "endColumnIndex": 6,
                                        }]
                                    }
                                },
                                "color": CHART_BLUE,
                                "colorStyle": {"rgbColor": CHART_BLUE},
                            },
                            {
                                "series": {
                                    "sourceRange": {
                                        "sources": [{
                                            "sheetId": SID_DASHBOARD,
                                            "startRowIndex": 12,
                                            "endRowIndex": 18,
                                            "startColumnIndex": 6,
                                            "endColumnIndex": 7,
                                        }]
                                    }
                                },
                                "color": CHART_GOLD,
                                "colorStyle": {"rgbColor": CHART_GOLD},
                            },
                        ],
                    },
                },
            }
        }
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def create_spreadsheet(sheets_service):
    body = {
        "properties": {"title": SHEET_TITLE},
        "sheets": [
            {"properties": {"sheetId": SID_SETTINGS, "title": "Settings", "index": 0}},
            {"properties": {"sheetId": SID_REGISTRATION, "title": "Registration", "index": 1}},
            {"properties": {"sheetId": SID_DASHBOARD, "title": "Dashboard", "index": 2}},
            {"properties": {"sheetId": SID_LIVE, "title": "📺 Live Payouts", "index": 3}},
            {"properties": {"sheetId": SID_INSTRUCTIONS, "title": "Instructions", "index": 4}},
            {"properties": {"sheetId": SID_BLINDS, "title": "⏱ Blinds Timer", "index": 5}},
        ],
    }
    result = sheets_service.spreadsheets().create(body=body).execute()
    return result["spreadsheetId"]


def populate_data(sheets_service, spreadsheet_id):
    data = []

    settings_rows = build_settings_data()
    data.append({
        "range": f"Settings!A1:{col_letter(7)}{len(settings_rows)}",
        "values": settings_rows,
    })

    reg_headers = build_registration_headers()
    data.append({
        "range": "Registration!A1:I1",
        "values": reg_headers,
    })

    reg_formulas_data = build_registration_formulas()
    data.append({
        "range": f"Registration!A2:I{LAST_PLAYER_ROW}",
        "values": reg_formulas_data,
    })

    dash_rows = build_dashboard_data()
    data.append({
        "range": f"Dashboard!A1:{col_letter(6)}{len(dash_rows)}",
        "values": dash_rows,
    })

    inst_rows = build_instructions_data()
    data.append({
        "range": f"Instructions!A1:A{len(inst_rows)}",
        "values": inst_rows,
    })

    blinds_rows = build_blinds_data()
    data.append({
        "range": f"'⏱ Blinds Timer'!A1:F{len(blinds_rows)}",
        "values": blinds_rows,
    })

    sheets_service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()


def apply_formatting(sheets_service, spreadsheet_id):
    requests = make_format_requests()
    requests.append(make_chart_request())

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def share_sheet(drive_service, spreadsheet_id):
    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()


def main():
    parser = argparse.ArgumentParser(
        description="Create the Poker Tournament Manager — Separate Prize Pools Edition."
    )
    parser.add_argument(
        "--credentials", "-c",
        default=DEFAULT_CREDENTIALS,
        help=f"Path to service-account credentials JSON (default: {DEFAULT_CREDENTIALS})",
    )
    args = parser.parse_args()

    creds_path = os.path.expanduser(args.credentials)
    if not os.path.exists(creds_path):
        print(f"Error: credentials file not found at {creds_path}")
        print(f"Place your Google service-account JSON at '{DEFAULT_CREDENTIALS}' or use --credentials")
        raise SystemExit(1)

    print("Authorizing with Google APIs...")
    sheets_service, drive_service = authorize(creds_path)

    print("Creating spreadsheet...")
    spreadsheet_id = create_spreadsheet(sheets_service)

    print("Populating data and formulas...")
    populate_data(sheets_service, spreadsheet_id)

    print("Applying formatting, validation, and chart...")
    apply_formatting(sheets_service, spreadsheet_id)

    print("Setting sharing permissions...")
    share_sheet(drive_service, spreadsheet_id)

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    print()
    print("Done! Your Separate Prize Pools sheet is ready.")
    print(f"SHEET_URL={url}")


if __name__ == "__main__":
    main()

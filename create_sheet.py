#!/usr/bin/env python3
"""
Create the Poker Tournament Manager Google Sheet from scratch.

Creates a fully-functional "Pro-Am Concurrent Flight" tournament sheet with:
  - Settings tab (configurable buy-ins, multipliers, payout tiers)
  - Registration tab (player entry with auto-calculated pots)
  - Dashboard tab (live totals, payout tables, chart data)
  - Live Payouts tab (column chart of prize pools)
  - Instructions tab (how-to guide)
  - Blinds Timer tab (placeholder)

Usage:
    pip install google-auth google-auth-oauthlib google-api-python-client
    python3 create_sheet.py [--credentials path/to/credentials.json]

The script prints the new sheet URL when finished.
"""

import argparse
import os

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_TITLE = "Poker Tournament Manager — Pro-Am Edition"

# Default path to service-account credentials JSON
DEFAULT_CREDENTIALS = "arborfam-hub-token.json"

# Number of player rows in Registration (2..31 → 30 players)
PLAYER_ROWS = 30
FIRST_PLAYER_ROW = 2
LAST_PLAYER_ROW = FIRST_PLAYER_ROW + PLAYER_ROWS - 1  # 31

# Sheet IDs (arbitrary but unique within the workbook)
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
DARK_BLUE = {"red": 0.1, "green": 0.2, "blue": 0.5}
CHART_BLUE = {"red": 0.26, "green": 0.52, "blue": 0.96}
CHART_GOLD = {"red": 0.98, "green": 0.74, "blue": 0.18}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def authorize(credentials_path: str):
    """Return an authorized Sheets + Drive service pair."""
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
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


def cell(col: int, row: int) -> str:
    """0-based (col, row) → 'A1'-style reference."""
    return f"{col_letter(col)}{row + 1}"


def bold_fmt():
    return {"textFormat": {"bold": True}}


def currency_fmt():
    return {"numberFormat": {"type": "NUMBER", "pattern": '$#,##0.00'}}


def pct_fmt():
    return {"numberFormat": {"type": "NUMBER", "pattern": "0"}}


def gc(row, col):
    """GridCoordinate dict."""
    return {"rowIndex": row, "columnIndex": col}


# ---------------------------------------------------------------------------
# Sheet builders — each returns a list of API requests
# ---------------------------------------------------------------------------

def build_settings_data():
    """Return rows for the Settings tab."""
    rows = []

    # Row 0: Header
    rows.append(["⚙️ SETTINGS"])

    # Rows 1-6: Inputs (label / value / notes)
    inputs = [
        ("Base Buy-in ($)", 40, "Standard entry for Low track"),
        ("High Roller Multiplier", 4, "High = base × this"),
        ("Bounty Cost ($)", 10, "Per-player bounty fee"),
        ("Top-Off Multiplier", 0.5, "Break top-off as fraction of buy-in"),
        ("Max Rebuys", 2, "Max rebuys per player"),
        ("Rake %", 0, "House rake (0 for home games)"),
    ]
    for label, val, note in inputs:
        rows.append([label, val, note])

    # Row 7: blank
    rows.append([])

    # Rows 8-13: Calculated values (label / arrow / formula)
    calcs = [
        ("High Roller Total", "=B2*B3"),
        ("Side Pot Per Person", "=B2*(B3-1)"),
        ("Low Top-Off Cost", "=B2*B5"),
        ("High Top-Off Cost", "=B2*B3*B5"),
        ("Low Total Entry", "=B2+B4"),
        ("High Total Entry", "=(B2*B3)+B4"),
    ]
    for label, formula in calcs:
        rows.append([label, "→", formula])

    # Row 14: blank
    rows.append([])

    # Row 15: Payout threshold header
    rows.append(["Min Players", "Max Players", "Places Paid",
                 "1st%", "2nd%", "3rd%", "4th%", "5th%"])

    # Rows 16-20: Payout tiers
    tiers = [
        [2, 4, 1, 100, 0, 0, 0, 0],
        [5, 8, 2, 65, 35, 0, 0, 0],
        [9, 15, 3, 50, 30, 20, 0, 0],
        [16, 25, 4, 45, 27, 17, 11, 0],
        [26, 999, 5, 40, 25, 16, 11, 8],
    ]
    for tier in tiers:
        rows.append(tier)

    return rows


def build_registration_headers():
    """Return the header row for Registration."""
    return [["Player Name", "Track", "Buy-in Paid?", "Rebuy Count",
             "Top-Off?", "Total Cash", "Main Pot", "Side Pot", "Bounty"]]


def reg_formulas(r: int) -> list:
    """Return formula strings for columns F-I at the given 1-based row."""
    # F: Total Cash
    f_total = (
        f'=IF(C{r},IF(B{r}="High",(Settings!$B$2*Settings!$B$3)+Settings!$B$4,'
        f"Settings!$B$2+Settings!$B$4),0)"
        f"+D{r}*IF(B{r}=\"High\",(Settings!$B$2*Settings!$B$3)+Settings!$B$4,"
        f"Settings!$B$2+Settings!$B$4)"
        f"+IF(E{r},IF(B{r}=\"High\",Settings!$B$2*Settings!$B$3*Settings!$B$5,"
        f"Settings!$B$2*Settings!$B$5),0)"
    )

    # G: Main Pot
    g_main = (
        f"=IF(C{r},Settings!$B$2,0)"
        f"+D{r}*Settings!$B$2"
        f"+IF(E{r},Settings!$B$2*Settings!$B$5,0)"
    )

    # H: Side Pot
    h_side = (
        f'=IF(B{r}="High",'
        f"IF(C{r},Settings!$B$2*(Settings!$B$3-1),0)"
        f"+D{r}*Settings!$B$2*(Settings!$B$3-1)"
        f"+IF(E{r},Settings!$B$2*Settings!$B$3*Settings!$B$5-Settings!$B$2*Settings!$B$5,0)"
        f",0)"
    )

    # I: Bounty
    i_bounty = (
        f"=IF(C{r},Settings!$B$4,0)"
        f"+D{r}*Settings!$B$4"
    )

    return [f_total, g_main, h_side, i_bounty]


def build_registration_formulas():
    """Return formula rows (one per player slot) for columns F-I."""
    rows = []
    for r in range(FIRST_PLAYER_ROW, LAST_PLAYER_ROW + 1):
        formulas = reg_formulas(r)
        # Columns A-E are blank (user fills); F-I are formulas
        rows.append(["", "", False, 0, False] + formulas)
    return rows


def build_dashboard_data():
    """Return rows for the Dashboard tab."""
    lr = LAST_PLAYER_ROW
    rows = []

    # Row 0: Header
    rows.append(["📊 DASHBOARD"])

    # Row 1: blank
    rows.append([])

    # Rows 2-12: Summary  (labels in A, formulas in B)
    summary = [
        ("Total Players", f'=COUNTIF(Registration!B2:B{lr},"Low")+COUNTIF(Registration!B2:B{lr},"High")'),
        ("Low (Fish) Count", f'=COUNTIF(Registration!B2:B{lr},"Low")'),
        ("High (Whale) Count", f'=COUNTIF(Registration!B2:B{lr},"High")'),
        ("", ""),  # blank row 5
        ("Total Cash in Box", f"=SUM(Registration!F2:F{lr})"),
        ("Bounty Pool", f"=SUM(Registration!I2:I{lr})"),
        ("Gross Prize Pool", f"=SUM(Registration!G2:G{lr})+SUM(Registration!H2:H{lr})"),
        ("Rake Amount", "=B9*Settings!B7/100"),
        ("Net Prize Pool", "=B9-B10"),
        ("Main Pot Total", f"=SUM(Registration!G2:G{lr})*(1-Settings!$B$7/100)"),
        ("Side Pot Total", f"=SUM(Registration!H2:H{lr})*(1-Settings!$B$7/100)"),
    ]
    for label, formula in summary:
        rows.append([label, formula])

    # Row 13: blank
    rows.append([])

    # ----- Main Pot payout table (rows 14-19, 0-indexed) -----
    rows.append(["MAIN POT PAYOUTS", "Place", "Pct%", "Amount ($)",
                 "Place", "🐟 Fish", "🐋 Whales"])

    places = ["1st", "2nd", "3rd", "4th", "5th"]
    # Settings payout table is in rows 17-21 (1-indexed), cols D-H (1st%-5th%)
    # We use $B$3 = total player count from Dashboard
    for i, place in enumerate(places):
        pct_col_letter = col_letter(3 + i)  # D=3, E=4, F=5, G=6, H=7
        # IFS lookup against Settings payout tiers using total player count
        pct_formula = (
            f"=IFERROR(IFS("
            f"$B$3>=Settings!A21,$B$3<=Settings!B21,Settings!{pct_col_letter}21,"
            f"$B$3>=Settings!A20,$B$3<=Settings!B20,Settings!{pct_col_letter}20,"
            f"$B$3>=Settings!A19,$B$3<=Settings!B19,Settings!{pct_col_letter}19,"
            f"$B$3>=Settings!A18,$B$3<=Settings!B18,Settings!{pct_col_letter}18,"
            f"$B$3>=Settings!A17,$B$3<=Settings!B17,Settings!{pct_col_letter}17"
            f"),0)"
        )
        amt_formula = f"=FLOOR($B$12*C{15 + 1 + i}/100,5)"
        # Chart helper columns E-G
        chart_place = place
        fish_formula = f"=D{15 + 1 + i}"
        whale_formula = f"=IF(ISNUMBER(D{23 + 1 + i}),D{23 + 1 + i},0)" if i < 4 else "=0"

        rows.append(["", place, pct_formula, amt_formula,
                     chart_place, fish_formula, whale_formula])

    # Row 20: blank
    rows.append([])
    # Row 21: blank
    rows.append([])

    # ----- Side Pot payout table (rows 22-26, 0-indexed) -----
    rows.append(["HIGH ROLLER SIDE POT", "Place", "Pct%", "Amount ($)"])

    side_places = ["1st", "2nd", "3rd", "4th"]
    for i, place in enumerate(side_places):
        pct_col_letter = col_letter(3 + i)
        pct_formula = (
            f"=IFERROR(IFS("
            f"$B$5>=Settings!A21,$B$5<=Settings!B21,Settings!{pct_col_letter}21,"
            f"$B$5>=Settings!A20,$B$5<=Settings!B20,Settings!{pct_col_letter}20,"
            f"$B$5>=Settings!A19,$B$5<=Settings!B19,Settings!{pct_col_letter}19,"
            f"$B$5>=Settings!A18,$B$5<=Settings!B18,Settings!{pct_col_letter}18,"
            f"$B$5>=Settings!A17,$B$5<=Settings!B17,Settings!{pct_col_letter}17"
            f"),0)"
        )
        amt_formula = f"=FLOOR($B$13*C{23 + 1 + i}/100,5)"
        rows.append(["", place, pct_formula, amt_formula])

    return rows


def build_instructions_data():
    """Return rows for the Instructions tab."""
    lines = [
        ["📖 INSTRUCTIONS"],
        [],
        ["HOW TO RUN TOURNAMENT NIGHT"],
        ["1. Open the Registration tab before players arrive."],
        ["2. Add each player's name in column A."],
        ['3. Select their track — Low ($40) or High ($160) — from the dropdown in column B.'],
        ['4. Check "Buy-in Paid?" when they hand you cash.'],
        ["5. Rebuys: increment the Rebuy Count (max 2) if a player buys back in."],
        ["6. Top-offs: check the Top-Off box during the break if a player adds chips."],
        ["7. Check the Dashboard tab for live totals — prize pools, payouts, bounties."],
        ["8. Pay out using the Dashboard payout tables:"],
        ["   - Main Pot: all players eligible"],
        ["   - Side Pot: High track (Whales) only"],
        ["   - Bounties: $10 per knockout from the bounty pool"],
        [],
        ["HOW TO START A NEW QUARTER"],
        ['1. Right-click the Registration tab → Duplicate.'],
        ['2. Rename the duplicate (e.g., "Registration Q3 2026").'],
        ["3. Clear all player data from the active Registration tab."],
        ["4. The Dashboard automatically recalculates."],
        ["   OR: Make a full copy of the entire spreadsheet for a fresh start."],
        [],
        ["SETTINGS REFERENCE"],
        ["Base Buy-in: standard entry for Low track (default $40)."],
        ["High Roller Multiplier: High track pays base × this (default 4× = $160)."],
        ["Bounty Cost: per-player fee added to bounty pool (default $10)."],
        ["Top-Off Multiplier: break top-off as fraction of buy-in (default 0.5×)."],
        ["Max Rebuys: maximum rebuys allowed per player (default 2)."],
        ["Rake %: house rake percentage (default 0% for home games)."],
        [],
        ["SOURCE CODE & UPDATES"],
        ["https://github.com/sagearbor/neighborhood-poker"],
    ]
    return lines


def build_blinds_data():
    """Return placeholder rows for the Blinds Timer tab."""
    return [
        ["⏱ BLINDS TIMER"],
        [],
        ["Coming soon! This tab will contain a blind structure and timer."],
        [],
        ["Suggested blind levels:"],
        ["Level 1: 25/50  (20 min)"],
        ["Level 2: 50/100  (20 min)"],
        ["Level 3: 100/200  (20 min)"],
        ["Level 4: 200/400  (15 min)"],
        ["Level 5: 300/600  (15 min)"],
        ["Level 6: 500/1000  (15 min)"],
    ]


# ---------------------------------------------------------------------------
# Formatting & validation request builders
# ---------------------------------------------------------------------------

def make_format_requests():
    """Return batchUpdate requests for formatting across all tabs."""
    requests = []

    # --- Settings tab ---

    # Header row bold
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Calculated cells (rows 8-13) gray background
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 8, "endRowIndex": 14,
                       "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"backgroundColor": LIGHT_GRAY}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Payout header row bold (row 15)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 15, "endRowIndex": 16},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # --- Registration tab ---

    # Header row bold
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_REGISTRATION, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Freeze row 1
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": SID_REGISTRATION,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # Currency format on F-I (cols 5-8)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_REGISTRATION,
                       "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                       "startColumnIndex": 5, "endColumnIndex": 9},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Data validation: Track dropdown (col B, rows 1-30 data area)
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

    # Data validation: Buy-in Paid checkbox (col C)
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                       "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                       "startColumnIndex": 2, "endColumnIndex": 3},
            "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
        }
    })

    # Data validation: Rebuy Count 0-2 (col D)
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

    # Data validation: Top-Off checkbox (col E)
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                       "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                       "startColumnIndex": 4, "endColumnIndex": 5},
            "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
        }
    })

    # Conditional formatting: Low → light blue
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

    # Conditional formatting: High → light gold
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

    # Header row bold
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Summary labels bold (col A, rows 2-12)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                       "startRowIndex": 2, "endRowIndex": 13,
                       "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Currency on summary B column (rows 6-12)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                       "startRowIndex": 6, "endRowIndex": 13,
                       "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Payout table section headers bold
    for row_idx in [14, 22]:
        requests.append({
            "repeatCell": {
                "range": {"sheetId": SID_DASHBOARD,
                           "startRowIndex": row_idx, "endRowIndex": row_idx + 1},
                "cell": {"userEnteredFormat": bold_fmt()},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        })

    # Currency on payout amounts (col D)
    for start, end in [(15, 20), (23, 27)]:
        requests.append({
            "repeatCell": {
                "range": {"sheetId": SID_DASHBOARD,
                           "startRowIndex": start, "endRowIndex": end,
                           "startColumnIndex": 3, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": currency_fmt()},
                "fields": "userEnteredFormat.numberFormat",
            }
        })

    # Currency on chart helper cols F-G
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                       "startRowIndex": 15, "endRowIndex": 20,
                       "startColumnIndex": 5, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # --- Live Payouts tab: hide gridlines ---
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

    # Section headers bold in Instructions
    for row_idx in [2, 15, 22, 30]:
        requests.append({
            "repeatCell": {
                "range": {"sheetId": SID_INSTRUCTIONS,
                           "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                           "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": bold_fmt()},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        })

    # --- Blinds Timer header bold ---
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    return requests


def make_chart_request():
    """Return an addChart request for the Live Payouts tab."""
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
                    "title": "🏆 Tonight's Prize Pools",
                    "basicChart": {
                        "chartType": "COLUMN",
                        "legendPosition": "BOTTOM_LEGEND",
                        "headerCount": 1,
                        "domains": [{
                            "domain": {
                                "sourceRange": {
                                    "sources": [{
                                        "sheetId": SID_DASHBOARD,
                                        "startRowIndex": 14,
                                        "endRowIndex": 20,
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
                                            "startRowIndex": 14,
                                            "endRowIndex": 20,
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
                                            "startRowIndex": 14,
                                            "endRowIndex": 20,
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
    """Create the spreadsheet with all tabs and return the spreadsheet ID."""
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
    """Write all cell data to every tab."""
    data = []

    # Settings
    settings_rows = build_settings_data()
    data.append({
        "range": f"Settings!A1:{col_letter(7)}{len(settings_rows)}",
        "values": settings_rows,
    })

    # Registration headers
    reg_headers = build_registration_headers()
    data.append({
        "range": "Registration!A1:I1",
        "values": reg_headers,
    })

    # Registration formulas (rows 2-31)
    reg_formulas_data = build_registration_formulas()
    data.append({
        "range": f"Registration!A2:I{LAST_PLAYER_ROW}",
        "values": reg_formulas_data,
    })

    # Dashboard
    dash_rows = build_dashboard_data()
    data.append({
        "range": f"Dashboard!A1:{col_letter(6)}{len(dash_rows)}",
        "values": dash_rows,
    })

    # Instructions
    inst_rows = build_instructions_data()
    data.append({
        "range": f"Instructions!A1:A{len(inst_rows)}",
        "values": inst_rows,
    })

    # Blinds Timer
    blinds_rows = build_blinds_data()
    data.append({
        "range": f"'⏱ Blinds Timer'!A1:A{len(blinds_rows)}",
        "values": blinds_rows,
    })

    sheets_service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()


def apply_formatting(sheets_service, spreadsheet_id):
    """Apply all formatting, validation, conditional formatting, and chart."""
    requests = make_format_requests()
    requests.append(make_chart_request())

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def share_sheet(drive_service, spreadsheet_id):
    """Make the sheet viewable by anyone with the link."""
    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()


def main():
    parser = argparse.ArgumentParser(
        description="Create the Poker Tournament Manager Google Sheet from scratch."
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
    print(f"Done! Your sheet is ready.")
    print(f"SHEET_URL={url}")


if __name__ == "__main__":
    main()

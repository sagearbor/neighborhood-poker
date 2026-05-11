#!/usr/bin/env python3
"""
Create the Poker Tournament Manager — Multi-Tier Edition Google Sheet.

Generalization of create_sheet_separate_pools.py from 2 tiers (Fish/Whale) to
up to 6 configurable tiers ("pots"). Each tier has its own buy-in amount, its
own separate prize pool, and its own placement payouts that scale with that
tier's player count. The $10 headhunter bounty (Settings!B10) is the only
cross-tier incentive.

Differences vs. create_sheet_separate_pools.py:
  - Settings has a 6-row "Pot Table" instead of fixed Base/Multiplier inputs.
    Fill any rows in any order; blank rows are inactive. Default tiers:
        🦐 Shrimp ($1) | 🐟 Fish ($10) | 🐠 Tuna ($40) | 🐋 Whale ($140)
  - Registration's Track dropdown auto-populates from non-blank pot names.
  - Dashboard generates one row per active tier showing pot total + 1st-5th
    place dollar amounts (scaled by that tier's player count via the same
    Settings payout-tier table).
  - Single-player tier auto-wins the pot (Option 1: no merging, no refund).
  - Apps Script blinds timer auto-installs (if the script.projects scope is
    granted — run setup_auth.py once to enable).

Usage:
    pip install google-auth google-auth-oauthlib google-api-python-client
    python3 create_sheet_multi_tier.py [--credentials path/to/credentials.json]
"""

import argparse
import json
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from apps_script_installer import try_install_timer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects",
]

SHEET_TITLE = "Poker Tournament Manager — Multi-Tier Edition"

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

# Pot table rows in Settings (1-indexed): up to 6 user-defined pots
POT_FIRST_ROW = 3
POT_LAST_ROW = 8
POT_COUNT = POT_LAST_ROW - POT_FIRST_ROW + 1  # 6

# Payout tier table rows in Settings (1-indexed): 6 tiers (1, 2-4, 5-8, ...)
TIER_FIRST_ROW = 18
TIER_LAST_ROW = 23

# Dashboard per-tier table rows (1-indexed): 6 tier display rows
DASH_TIER_HEADER_ROW = 10  # sub-header for the per-pot table
DASH_TIER_FIRST_ROW = 11
DASH_TIER_LAST_ROW = DASH_TIER_FIRST_ROW + POT_COUNT - 1  # 16

# Colors
WHITE = {"red": 1, "green": 1, "blue": 1}
LIGHT_GRAY = {"red": 0.93, "green": 0.93, "blue": 0.93}
LIGHT_BLUE = {"red": 0.85, "green": 0.92, "blue": 1.0}
LIGHT_GOLD = {"red": 1.0, "green": 0.95, "blue": 0.8}
SETTINGS_BG = {"red": 0.93, "green": 0.96, "blue": 1.0}
DARK_HEADER = {"red": 0.15, "green": 0.15, "blue": 0.3}
ORANGE_BREAK = {"red": 1.0, "green": 0.8, "blue": 0.4}
LIGHT_ROW = {"red": 0.95, "green": 0.95, "blue": 1.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def authorize(credentials_path: str):
    """Load a user OAuth token JSON. Returns (creds, sheets, drive)."""
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
    return creds, sheets, drive


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


def _tier_lookup_ifs(count_cell: str, pct_col_letter: str) -> str:
    """IFS lookup against Settings payout tier table (rows TIER_FIRST_ROW..LAST).
    Each tier wrapped in AND() so IFS returns the percentage, not a boolean."""
    pairs = []
    for tier_row in range(TIER_LAST_ROW, TIER_FIRST_ROW - 1, -1):
        cond = (
            f"AND({count_cell}>=Settings!$A${tier_row},"
            f"{count_cell}<=Settings!$B${tier_row})"
        )
        val = f"Settings!${pct_col_letter}${tier_row}"
        pairs.append(f"{cond},{val}")
    return f"IFERROR(IFS({','.join(pairs)}),0)"


# ---------------------------------------------------------------------------
# Settings tab
# ---------------------------------------------------------------------------

def build_settings_data():
    """Settings tab layout:
      Row 1:        ⚙️ SETTINGS
      Row 2:        Pot table header (Pot Name | Buy-in | Note)
      Rows 3-8:     6 user-fillable pot rows (4 default-filled, 2 blank)
      Row 9:        blank
      Row 10-13:    Bounty / Top-Off / Max Rebuys / Rake
      Row 14:       blank
      Row 15:       Suggested Bounty (calc)
      Row 16:       blank
      Row 17:       Payout tier header
      Rows 18-23:   6 payout tiers (1, 2-4, 5-8, 9-15, 16-25, 26+)
    """
    rows = []

    # Row 1
    rows.append(["⚙️ SETTINGS"])

    # Row 2: pot table header (3 visible cols). The "active filter" helper
    # lives off to the right in col I (written separately) so col D stays
    # blank for these rows and the Note in C can overflow naturally.
    rows.append(["Pot Name", "Buy-in ($)", "Note"])

    # Rows 3-8: 6 pot rows in monetary order with two optional in-between tiers.
    # Active tiers (Buy-in set) flow through; the Crab/Dolphin rows are pre-
    # filled name+note but Buy-in blank, so they're inert until activated.
    default_pots = [
        ("🦐 Shrimp", 1, "Casual / learning"),
        ("🦀 Crab", "", "Optional — fill Buy-in to activate (~$5 suggested)"),
        ("🐟 Fish", 10, "Low-stakes fun"),
        ("🐠 Tuna", 40, "Mid-stakes"),
        ("🐬 Dolphin", "", "Optional — fill Buy-in to activate (~$75 suggested)"),
        ("🐋 Whale", 140, "High-stakes"),
    ]
    for name, buyin, note in default_pots:
        rows.append([name, buyin, note])

    # Row 9: blank
    rows.append([])

    # Rows 10-13: configuration
    config = [
        ("Bounty ($)", 10, "Headhunter chip per knockout"),
        ("Top-Off Multiplier", 0.5, "Break top-off as fraction of buy-in"),
        ("Max Rebuys", 2, "Max rebuys per player"),
        ("Rake %", 0, "House rake (0 for home games)"),
    ]
    for label, val, note in config:
        rows.append([label, val, note])

    # Row 14: blank
    rows.append([])

    # Row 15: Suggested Bounty (20% of smallest active pot buy-in, rounded, min $1)
    rows.append([
        "Suggested Bounty",
        "→",
        f"=IFERROR(MAX(1,ROUND(SMALL(FILTER($B${POT_FIRST_ROW}:$B${POT_LAST_ROW},"
        f"$B${POT_FIRST_ROW}:$B${POT_LAST_ROW}>0),1)*0.2,0)),\"\")",
        "20% of smallest active pot buy-in",
    ])

    # Row 16: blank
    rows.append([])

    # Row 17: payout tier header
    rows.append(["Min Players", "Max Players", "Places Paid",
                 "1st%", "2nd%", "3rd%", "4th%", "5th%"])

    # Rows 18-23: 6 payout tiers
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
    """Registration layout (1-indexed cols):
      A: Player Name (input)
      B: Pot (dropdown)
      C: Owed ($) (formula — what cashier should collect right now)
      D: Buy-in Paid? (checkbox)
      E: Rebuy Count (number 0-2)
      F: Top-Off? (checkbox)
      G: Total Cash (formula — actually collected, gated on Paid)
      H: Pot Contribution (formula — buy-in portion only)
      I: Bounty (formula — bounty portion)
    """
    return [["Player Name", "Pot", "Owed ($)", "Buy-in Paid?", "Rebuy Count",
             "Top-Off?", "Total Cash", "Pot Contribution", "Bounty"]]


def reg_formulas(r: int) -> list:
    """Return formulas for [C (Owed), G (Total Cash), H (Pot Contribution),
    I (Bounty)] at 1-based row r."""
    pot_lookup = (
        f"VLOOKUP(B{r},Settings!$A${POT_FIRST_ROW}:$B${POT_LAST_ROW},2,FALSE)"
    )
    bounty = "Settings!$B$10"
    topoff_mult = "Settings!$B$11"

    # C: Owed — expected total at this moment regardless of Paid status.
    # Shows what the cashier should be collecting (initial buy-in + bounty,
    # plus any rebuys, plus top-off if checked). 0 until a Pot is picked.
    c_owed = (
        f"=IFERROR("
        f"({pot_lookup}+{bounty})"
        f"+E{r}*({pot_lookup}+{bounty})"
        f"+IF(F{r},{pot_lookup}*{topoff_mult},0)"
        f",0)"
    )

    # G: Total Cash — actually-collected (buy-in only counts when Paid is checked)
    g_total = (
        f"=IFERROR("
        f"IF(D{r},{pot_lookup}+{bounty},0)"
        f"+E{r}*({pot_lookup}+{bounty})"
        f"+IF(F{r},{pot_lookup}*{topoff_mult},0)"
        f",0)"
    )

    # H: Pot Contribution — buy-in portion only (no bounty), gated on Paid
    h_pot = (
        f"=IFERROR("
        f"IF(D{r},{pot_lookup},0)"
        f"+E{r}*{pot_lookup}"
        f"+IF(F{r},{pot_lookup}*{topoff_mult},0)"
        f",0)"
    )

    # I: Bounty — independent of pot
    i_bounty = f"=IF(D{r},{bounty},0)+E{r}*{bounty}"

    return [c_owed, g_total, h_pot, i_bounty]


def build_registration_formulas():
    rows = []
    for r in range(FIRST_PLAYER_ROW, LAST_PLAYER_ROW + 1):
        c_owed, g_total, h_pot, i_bounty = reg_formulas(r)
        # A, B, C, D, E, F, G, H, I
        rows.append(["", "", c_owed, False, 0, False, g_total, h_pot, i_bounty])
    return rows


# ---------------------------------------------------------------------------
# Dashboard tab
# ---------------------------------------------------------------------------

def build_dashboard_data():
    """Dashboard layout (Python indices = sheet rows minus 1):
      Row 1:       📊 DASHBOARD
      Row 2:       blank
      Row 3:       Total Players       | =COUNTA(Reg!B2:B31)
      Row 4:       Total Cash in Box   | =SUM(Reg!F)
      Row 5:       Bounty Pool         | =SUM(Reg!H)
      Row 6:       Rake Amount         | =SUM(Reg!G) * rake
      Row 7:       Net Prize Pool      | =SUM(Reg!G) * (1-rake)
      Row 8:       blank
      Row 9:       PER-POT BREAKDOWN
      Row 10:      sub-header: Pot Name | Players | Pot Total | 1st | 2nd | 3rd | 4th | 5th
      Rows 11-16:  6 tier rows (one per Settings row 3-8)
    """
    lr = LAST_PLAYER_ROW
    rows = []

    rows.append(["📊 DASHBOARD"])
    rows.append([])

    rows.append(["Total Players", f"=COUNTA(Registration!B2:B{lr})"])
    rows.append(["Total Cash in Box", f"=SUM(Registration!G2:G{lr})"])
    rows.append(["Bounty Pool", f"=SUM(Registration!I2:I{lr})"])
    rows.append(["Rake Amount",
                 f"=SUM(Registration!H2:H{lr})*Settings!$B$13/100"])
    rows.append(["Net Prize Pool",
                 f"=SUM(Registration!H2:H{lr})*(1-Settings!$B$13/100)"])

    rows.append([])
    rows.append(["PER-POT BREAKDOWN"])

    # Sub-header (sheet row 10 = Python index 9)
    rows.append(["Pot Name", "Players", "Pot Total",
                 "1st", "2nd", "3rd", "4th", "5th"])

    # 6 tier rows (sheet rows 11-16 = Python indices 10-15).
    # Use the helper "active" col D as the gate: tiers with blank Buy-in
    # render as fully blank Dashboard rows (no count, no pot, no payouts).
    for offset in range(POT_COUNT):
        settings_row = POT_FIRST_ROW + offset  # 3..8
        dash_row = DASH_TIER_FIRST_ROW + offset  # 11..16

        active_cell = f"Settings!$I${settings_row}"  # helper: name if active, else ""

        name_formula = f"={active_cell}"
        count_formula = (
            f"=IF({active_cell}=\"\",\"\","
            f"COUNTIF(Registration!$B$2:$B${lr},{active_cell}))"
        )
        total_formula = (
            f"=IF({active_cell}=\"\",\"\","
            f"SUMIF(Registration!$B$2:$B${lr},{active_cell},"
            f"Registration!$H$2:$H${lr})*(1-Settings!$B$13/100))"
        )

        # Place columns D-H (1st-5th)
        place_formulas = []
        for place_idx in range(5):
            pct_col = col_letter(3 + place_idx)  # D, E, F, G, H
            count_cell = f"$B${dash_row}"
            total_cell = f"$C${dash_row}"
            ifs = _tier_lookup_ifs(count_cell, pct_col)
            place_formulas.append(
                f"=IFERROR(IF({count_cell}<=0,\"\","
                f"FLOOR({total_cell}*({ifs})/100,5)),\"\")"
            )

        rows.append([name_formula, count_formula, total_formula] + place_formulas)

    return rows


# ---------------------------------------------------------------------------
# Instructions tab
# ---------------------------------------------------------------------------

def build_instructions_data():
    lines = [
        ["📖 INSTRUCTIONS — MULTI-TIER EDITION"],
        [],
        ["HOW THIS WORKS"],
        ["This is a variable buy-in tournament with up to 6 separate pots."],
        ["Each player picks a pot tier from the Registration dropdown — they"],
        ["pay that tier's buy-in plus the bounty chip. Each pot pays out"],
        ["independently to the top finishers WITHIN that tier."],
        [""],
        ["The bounty (Settings!B10) is the only cross-tier money: $10 (or"],
        ["whatever you set) per knockout, regardless of victim's tier."],
        [],
        ["CONFIGURING POTS"],
        ["Edit the Pot Table at Settings rows 3-8. Fill in any 2-6 rows;"],
        ["leave the rest blank. Order doesn't matter. Defaults:"],
        ["  🦐 Shrimp $1  |  🐟 Fish $10  |  🐠 Tuna $40  |  🐋 Whale $140"],
        ["The Registration dropdown auto-updates from filled pot names."],
        [],
        ["HOW TO RUN TOURNAMENT NIGHT"],
        ["1. Set up your pot tiers in Settings before players arrive."],
        ["2. In Registration, add each player's name + pick their pot tier."],
        ['3. Check "Buy-in Paid?" when they hand you cash.'],
        ["4. Rebuys: increment Rebuy Count (max 2) if a player buys back in."],
        ["5. Top-offs: check the Top-Off box during the break if they add chips."],
        ["6. Watch the Dashboard — each tier shows count, pot, and 1st-5th payouts."],
        ["7. Pay out at bust time using each tier's payout row."],
        ["   - Top N finishers per tier cash (N depends on tier player count)"],
        ["   - Bounty: $10 per knockout from the bounty pool (any tier)"],
        [],
        ["HOW PLACES PAID SCALES (per tier, independently)"],
        ["  1 player:    1 place paid (100%)"],
        ["  2-4:         1 place (100%)"],
        ["  5-8:         2 places (65/35)"],
        ["  9-15:        3 places (50/30/20)"],
        ["  16-25:       4 places (45/27/17/11)"],
        ["  26+:         5 places (40/25/16/11/8)"],
        [],
        ["BLINDS TIMER"],
        ["The 🃏 Poker Timer menu appears in the menu bar automatically"],
        ["(installed via Apps Script API when this sheet was created)."],
        ["Schedule lives in the ⏱ Blinds Timer tab — edit there to change blinds."],
        [],
        ["SOURCE CODE"],
        ["https://github.com/sagearbor/neighborhood-poker"],
    ]
    return lines


# ---------------------------------------------------------------------------
# Blinds Timer tab (full schedule inline)
# ---------------------------------------------------------------------------

def build_blinds_data():
    rows = []

    rows.append(["⏱ BLINDS TIMER", "", "", "", "", ""])
    rows.append(["Starting Stack:", "10,000", "", "Ante starts at level:", 5, ""])
    rows.append(["Level duration default:", "20 min", "", "", "", ""])
    rows.append(["💡 Highlight the current row manually as you progress",
                 "", "", "", "", ""])

    rows.append([])

    rows.append(["Level", "Small Blind", "Big Blind", "Ante",
                 "Duration (min)", "Total Time Elapsed"])

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

    data_start_row = 7
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
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Settings column widths: roomy Note column + hide the helper at col I.
    for col_idx, width in [(0, 160), (1, 110), (2, 320)]:  # A, B, C
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": SID_SETTINGS, "dimension": "COLUMNS",
                          "startIndex": col_idx, "endIndex": col_idx + 1},
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })

    # Hide col I (the active-filter helper).
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": SID_SETTINGS, "dimension": "COLUMNS",
                      "startIndex": 8, "endIndex": 9},
            "properties": {"hiddenByUser": True},
            "fields": "hiddenByUser",
        }
    })

    # Pot table header bold (row 2 / index 1)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 1, "endRowIndex": 2,
                      "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Pot table rows (rows 3-8 / indices 2-7): subtle background
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS,
                      "startRowIndex": POT_FIRST_ROW - 1, "endRowIndex": POT_LAST_ROW,
                      "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"backgroundColor": SETTINGS_BG}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Buy-in column currency format
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS,
                      "startRowIndex": POT_FIRST_ROW - 1, "endRowIndex": POT_LAST_ROW,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Suggested Bounty calc row (row 15 / index 14): gray background
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 14, "endRowIndex": 15,
                      "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": LIGHT_GRAY}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Payout tier header bold (row 17 / index 16)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_SETTINGS, "startRowIndex": 16, "endRowIndex": 17},
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

    # Currency on C (Owed) and G-I (Total Cash, Pot Contribution, Bounty)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 2, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 6, "endColumnIndex": 9},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Pot dropdown sourced from Settings col I (hidden helper "active" column).
    # Tiers with blank Buy-in show "" there and are skipped from the dropdown.
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "rule": {
                "condition": {
                    "type": "ONE_OF_RANGE",
                    "values": [{
                        "userEnteredValue":
                            f"=Settings!$I${POT_FIRST_ROW}:$I${POT_LAST_ROW}"
                    }],
                },
                "showCustomUi": True,
                "strict": True,
            },
        }
    })

    # Buy-in Paid? checkbox — col D (index 3, shifted from C)
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 3, "endColumnIndex": 4},
            "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
        }
    })

    # Rebuy Count 0-2 — col E (index 4, shifted from D)
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 4, "endColumnIndex": 5},
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

    # Top-Off? checkbox — col F (index 5, shifted from E)
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": SID_REGISTRATION,
                      "startRowIndex": 1, "endRowIndex": LAST_PLAYER_ROW,
                      "startColumnIndex": 5, "endColumnIndex": 6},
            "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
        }
    })

    # Alternating row banding on Registration data rows (cols A-I)
    requests.append({
        "addBanding": {
            "bandedRange": {
                "range": {"sheetId": SID_REGISTRATION,
                          "startRowIndex": 0, "endRowIndex": LAST_PLAYER_ROW,
                          "startColumnIndex": 0, "endColumnIndex": 9},
                "rowProperties": {
                    "headerColor": LIGHT_GRAY,
                    "firstBandColor": WHITE,
                    "secondBandColor": LIGHT_ROW,
                },
            }
        }
    })

    # --- Dashboard tab ---
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Summary labels bold (col A, rows 3-7)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                      "startRowIndex": 2, "endRowIndex": 7,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": bold_fmt()},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Currency on summary col B (rows 4-7, the dollar rows)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                      "startRowIndex": 3, "endRowIndex": 7,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": currency_fmt()},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # "PER-POT BREAKDOWN" header bold (row 9 / index 8)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                      "startRowIndex": 8, "endRowIndex": 9,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 12}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # Per-pot sub-header (row 10 / index 9) bold + light bg
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                      "startRowIndex": DASH_TIER_HEADER_ROW - 1,
                      "endRowIndex": DASH_TIER_HEADER_ROW,
                      "startColumnIndex": 0, "endColumnIndex": 8},
            "cell": {"userEnteredFormat": {
                "backgroundColor": SETTINGS_BG,
                "textFormat": {"bold": True},
            }},
            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat",
        }
    })

    # Currency on per-pot data rows, cols C-H (rows 11-16)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_DASHBOARD,
                      "startRowIndex": DASH_TIER_FIRST_ROW - 1,
                      "endRowIndex": DASH_TIER_LAST_ROW,
                      "startColumnIndex": 2, "endColumnIndex": 8},
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

    # --- Blinds Timer (same formatting as variant 2) ---
    col_widths = [(0, 200), (1, 120), (2, 120), (3, 80), (4, 140), (5, 180)]
    for col_idx, width in col_widths:
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": SID_BLINDS, "dimension": "COLUMNS",
                          "startIndex": col_idx, "endIndex": col_idx + 1},
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })

    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 0, "endRowIndex": 22},
            "cell": {"userEnteredFormat": {"textFormat": {"fontSize": 14}}},
            "fields": "userEnteredFormat.textFormat.fontSize",
        }
    })

    # Title bold 18pt
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 18}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # Settings rows
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

    # Note row italic
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 3, "endRowIndex": 4,
                      "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"textFormat": {"italic": True, "fontSize": 12}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # Header row
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

    # Data rows: alternating + breaks
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

    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS,
                      "startRowIndex": data_start, "endRowIndex": data_start + 15,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT"}},
            "fields": "userEnteredFormat.horizontalAlignment",
        }
    })

    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS,
                      "startRowIndex": data_start, "endRowIndex": data_start + 15,
                      "startColumnIndex": 1, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

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
    """Chart on Live Payouts: column chart with tier names on X-axis and
    1st-5th place dollar amounts as 5 series. Blank tiers render as empty bars."""
    series = []
    chart_colors = [
        {"red": 0.95, "green": 0.20, "blue": 0.20},  # red (1st)
        {"red": 0.20, "green": 0.55, "blue": 0.95},  # blue (2nd)
        {"red": 0.20, "green": 0.75, "blue": 0.30},  # green (3rd)
        {"red": 0.95, "green": 0.65, "blue": 0.15},  # orange (4th)
        {"red": 0.60, "green": 0.30, "blue": 0.75},  # purple (5th)
    ]
    # Place columns D-H (0-indexed 3-7); header row 10 (0-indexed 9) for legend.
    for place_idx, color in enumerate(chart_colors):
        col = 3 + place_idx
        series.append({
            "series": {
                "sourceRange": {
                    "sources": [{
                        "sheetId": SID_DASHBOARD,
                        "startRowIndex": DASH_TIER_HEADER_ROW - 1,
                        "endRowIndex": DASH_TIER_LAST_ROW,
                        "startColumnIndex": col,
                        "endColumnIndex": col + 1,
                    }]
                }
            },
            "color": color,
            "colorStyle": {"rgbColor": color},
        })

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
                    "title": "🏆 Tonight's Prize Pools — Per-Pot Payouts",
                    "basicChart": {
                        "chartType": "COLUMN",
                        "legendPosition": "BOTTOM_LEGEND",
                        "headerCount": 1,
                        "domains": [{
                            "domain": {
                                "sourceRange": {
                                    "sources": [{
                                        "sheetId": SID_DASHBOARD,
                                        "startRowIndex": DASH_TIER_HEADER_ROW - 1,
                                        "endRowIndex": DASH_TIER_LAST_ROW,
                                        "startColumnIndex": 0,
                                        "endColumnIndex": 1,
                                    }]
                                }
                            }
                        }],
                        "series": series,
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

    # Helper "active filter" formulas in col I rows 3-8 (hidden column).
    # =IF(B>0, A, "") — name flows through only when Buy-in is set.
    helper_formulas = [
        [f'=IF(B{POT_FIRST_ROW + i}>0,A{POT_FIRST_ROW + i},"")']
        for i in range(POT_COUNT)
    ]
    data.append({
        "range": f"Settings!I{POT_FIRST_ROW}:I{POT_LAST_ROW}",
        "values": helper_formulas,
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
        "range": f"Dashboard!A1:{col_letter(7)}{len(dash_rows)}",
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
        description="Create the Poker Tournament Manager — Multi-Tier Edition."
    )
    parser.add_argument(
        "--credentials", "-c",
        default=DEFAULT_CREDENTIALS,
        help=f"Path to OAuth token JSON (default: {DEFAULT_CREDENTIALS})",
    )
    parser.add_argument(
        "--no-timer-install",
        action="store_true",
        help="Skip Apps Script auto-install (fall back to manual setup).",
    )
    args = parser.parse_args()

    creds_path = os.path.expanduser(args.credentials)
    if not os.path.exists(creds_path):
        print(f"Error: credentials file not found at {creds_path}")
        raise SystemExit(1)

    print("Authorizing with Google APIs...")
    creds, sheets_service, drive_service = authorize(creds_path)

    print("Creating spreadsheet...")
    spreadsheet_id = create_spreadsheet(sheets_service)

    print("Populating data and formulas...")
    populate_data(sheets_service, spreadsheet_id)

    print("Applying formatting, validation, and chart...")
    apply_formatting(sheets_service, spreadsheet_id)

    print("Setting sharing permissions...")
    share_sheet(drive_service, spreadsheet_id)

    if not args.no_timer_install:
        print("Installing Apps Script blinds timer...")
        try_install_timer(creds, spreadsheet_id)

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    print()
    print("Done! Your Multi-Tier sheet is ready.")
    print(f"SHEET_URL={url}")


if __name__ == "__main__":
    main()

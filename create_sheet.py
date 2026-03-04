#!/usr/bin/env python3
"""Create the Poker Tournament Manager Google Sheet with all tabs, formulas, and formatting."""

import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = "/Users/sophie.arborbot/.openclaw/workspace/arborfam-hub-token.json"

def get_creds():
    with open(TOKEN_PATH) as f:
        data = json.load(f)
    creds = Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"],
    )
    return creds

def main():
    creds = get_creds()
    sheets = build("sheets", "v4", credentials=creds)

    # ── Create spreadsheet with 4 tabs ──
    body = {
        "properties": {"title": "Poker Tournament Manager — Q2 2026"},
        "sheets": [
            {"properties": {"sheetId": 0, "title": "Settings", "index": 0}},
            {"properties": {"sheetId": 1, "title": "Registration", "index": 1}},
            {"properties": {"sheetId": 2, "title": "Dashboard", "index": 2}},
            {"properties": {"sheetId": 3, "title": "Instructions", "index": 3}},
        ],
    }
    ss = sheets.spreadsheets().create(body=body).execute()
    ss_id = ss["spreadsheetId"]
    url = ss["spreadsheetUrl"]
    print(f"SHEET_ID={ss_id}")
    print(f"SHEET_URL={url}")

    # Save refreshed token
    if creds.token:
        with open(TOKEN_PATH) as f:
            data = json.load(f)
        data["token"] = creds.token
        if creds.expiry:
            data["expiry"] = creds.expiry.isoformat() + "Z"
        with open(TOKEN_PATH, "w") as f:
            json.dump(data, f)

    # ── Settings Tab ──
    settings_data = [
        # Row 1: Headers
        ["Setting", "Value", "Calculated", "Description"],
        # Row 2
        ["Base Buy-In", 40, '=B2*B3', "High_Total_BuyIn"],
        # Row 3
        ["High Roller Multiplier", 4, '=B2*(B3-1)', "Side_Pot_Per_Person"],
        # Row 4
        ["Bounty Cost", 10, '=B2*B5', "Low_TopOff"],
        # Row 5
        ["Top-Off Multiplier", 0.5, '=C2*B5', "High_TopOff"],
        # Row 6
        ["Max Rebuys", 2, '=B2+B4', "Low_Total_Entry"],
        # Row 7
        ["Rake Percent", 0, '=C2+B4', "High_Total_Entry"],
        # Rows 8-13 blank
        [], [], [], [], [], [],
        # Row 14: Payout header
        ["Min Players", "Max Players", "Places Paid", "1st%", "2nd%", "3rd%", "4th%", "5th%"],
        # Row 15-19: Payout data
        [2, 4, 1, 100, 0, 0, 0, 0],
        [5, 8, 2, 65, 35, 0, 0, 0],
        [9, 15, 3, 50, 30, 20, 0, 0],
        [16, 25, 4, 45, 27, 17, 11, 0],
        [26, 999, 5, 40, 25, 16, 11, 8],
    ]

    # ── Registration Tab ──
    reg_headers = [
        "Player Name", "Track", "Buy-in Paid?", "Rebuy Count",
        "Top-Off?", "Total Cash Collected", "Main Pot Contribution",
        "Side Pot Contribution", "Bounty Contribution"
    ]

    reg_rows = [reg_headers]
    for r in range(2, 32):  # rows 2-31
        reg_rows.append([
            "",  # A: Player Name
            "",  # B: Track
            False,  # C: Buy-in Paid? (checkbox)
            0,  # D: Rebuy Count
            False,  # E: Top-Off? (checkbox)
            # F: Total Cash Collected
            f'=IF(C{r},IF(B{r}="High",Settings!$C$7,Settings!$C$6),0)+D{r}*IF(B{r}="High",Settings!$C$7,Settings!$C$6)+IF(E{r},IF(B{r}="High",Settings!$C$5,Settings!$C$4),0)',
            # G: Main Pot Contribution
            f'=IF(C{r},Settings!$B$2,0)+D{r}*Settings!$B$2+IF(E{r},Settings!$C$4,0)',
            # H: Side Pot Contribution
            f'=IF(B{r}="High",IF(C{r},Settings!$C$3,0)+D{r}*Settings!$C$3+IF(E{r},Settings!$C$5-Settings!$C$4,0),0)',
            # I: Bounty Contribution
            f'=IF(C{r},Settings!$B$4,0)+D{r}*Settings!$B$4',
        ])

    # ── Dashboard Tab ──
    dashboard_data = [
        ["TOURNAMENT DASHBOARD", "", ""],
        [],
        ["Total Players", f'=COUNTIF(Registration!B2:B31,"Low")+COUNTIF(Registration!B2:B31,"High")'],
        ["Low Track Count", f'=COUNTIF(Registration!B2:B31,"Low")'],
        ["High (Whale) Track Count", f'=COUNTIF(Registration!B2:B31,"High")'],
        [],
        ["Total Cash in Box", '=SUM(Registration!F2:F31)'],
        ["Bounty Pool", '=SUM(Registration!I2:I31)'],
        ["Gross Prize Pool", '=SUM(Registration!G2:G31)+SUM(Registration!H2:H31)'],
        ["Rake Amount", '=B9*Settings!B7/100'],
        ["Net Prize Pool", '=B9-B10'],
        ["Main Pot Total", '=SUM(Registration!G2:G31)*(1-Settings!$B$7/100)'],
        ["Side Pot Total", '=SUM(Registration!H2:H31)*(1-Settings!$B$7/100)'],
        [],
        # Row 15: Main Pot Payout header
        ["MAIN POT PAYOUTS", "Place", "Pct", "Amount"],
        # Use IFS to look up from payout thresholds based on total player count
        # Total players in B3
    ]
    # Main Pot payout rows (rows 16-20, places 1st-5th)
    pct_cols = ["D", "E", "F", "G", "H"]  # columns in Settings payout table for 1st%-5th%
    for i, place in enumerate(["1st", "2nd", "3rd", "4th", "5th"]):
        col = pct_cols[i]
        # VLOOKUP-style: find the right row in Settings!A15:H19 based on player count
        pct_formula = (
            f'=IFS($B$3>=Settings!A19,$B$3<=Settings!B19,Settings!{col}19,'
            f'$B$3>=Settings!A18,$B$3<=Settings!B18,Settings!{col}18,'
            f'$B$3>=Settings!A17,$B$3<=Settings!B17,Settings!{col}17,'
            f'$B$3>=Settings!A16,$B$3<=Settings!B16,Settings!{col}16,'
            f'$B$3>=Settings!A15,$B$3<=Settings!B15,Settings!{col}15)'
        )
        # Actually let me use a simpler approach with nested IFS checking ranges
        pct_formula = (
            f'=IFERROR(IFS('
            f'AND($B$3>=Settings!A19,$B$3<=Settings!B19),Settings!{col}19,'
            f'AND($B$3>=Settings!A18,$B$3<=Settings!B18),Settings!{col}18,'
            f'AND($B$3>=Settings!A17,$B$3<=Settings!B17),Settings!{col}17,'
            f'AND($B$3>=Settings!A16,$B$3<=Settings!B16),Settings!{col}16,'
            f'AND($B$3>=Settings!A15,$B$3<=Settings!B15),Settings!{col}15'
            f'),0)'
        )
        amt_formula = f'=C{16+i}/100*$B$12'
        dashboard_data.append(["", place, pct_formula, amt_formula])

    dashboard_data.append([])
    # Row 22: Side Pot header
    dashboard_data.append(["HIGH ROLLER SIDE POT — Whales Only", "Place", "Pct", "Amount"])
    # Side Pot payout rows (rows 23-27, uses High track count = B5)
    for i, place in enumerate(["1st", "2nd", "3rd", "4th", "5th"]):
        col = pct_cols[i]
        pct_formula = (
            f'=IFERROR(IFS('
            f'AND($B$5>=Settings!A19,$B$5<=Settings!B19),Settings!{col}19,'
            f'AND($B$5>=Settings!A18,$B$5<=Settings!B18),Settings!{col}18,'
            f'AND($B$5>=Settings!A17,$B$5<=Settings!B17),Settings!{col}17,'
            f'AND($B$5>=Settings!A16,$B$5<=Settings!B16),Settings!{col}16,'
            f'AND($B$5>=Settings!A15,$B$5<=Settings!B15),Settings!{col}15'
            f'),0)'
        )
        row_num = 23 + i
        amt_formula = f'=C{row_num}/100*$B$13'
        dashboard_data.append(["", place, pct_formula, amt_formula])

    # ── Instructions Tab ──
    instructions_data = [
        ["POKER TOURNAMENT MANAGER — INSTRUCTIONS"],
        [],
        ["GETTING STARTED"],
        ["1. Go to the Settings tab and adjust values if needed (buy-in, multiplier, bounty, etc.)"],
        ["2. The calculated fields (gray cells) update automatically — don't edit them."],
        [],
        ["TOURNAMENT NIGHT"],
        ["1. Open the Registration tab."],
        ["2. Enter each player's name in column A."],
        ["3. Select their track (Low or High) from the dropdown in column B."],
        ["4. Check the 'Buy-in Paid?' box when they pay."],
        ["5. If a player rebuys, increment their Rebuy Count (max 2 by default)."],
        ["6. If a player tops off during the break, check the Top-Off box."],
        ["7. Columns F-I calculate automatically — Total Cash, Main Pot, Side Pot, and Bounty contributions."],
        ["8. Switch to the Dashboard tab to see live totals and payout amounts."],
        [],
        ["PAYING OUT"],
        ["1. The Dashboard shows Main Pot payouts for ALL players and Side Pot payouts for HIGH track only."],
        ["2. Pay bounties from the Bounty Pool ($10 per knockout by default)."],
        ["3. Verify: Total Cash in Box = Main Pot + Side Pot + Bounty Pool + Rake."],
        [],
        ["STARTING A NEW QUARTER"],
        ["1. Right-click the Registration tab and choose 'Duplicate'."],
        ["2. Rename the duplicate to the new quarter (e.g., 'Registration Q3 2026')."],
        ["3. Clear player data from the original Registration tab for the new quarter."],
        ["4. The Dashboard will automatically reflect the active Registration tab."],
        [],
        ["SHARING"],
        ["1. Share the sheet with co-organizers as Editors."],
        ["2. Share with players as Viewers if you want them to see the dashboard."],
        ["3. Consider protecting the Settings and Dashboard tabs (Data > Protect sheets)."],
        [],
        ["SETTINGS REFERENCE"],
        ["Base Buy-In: The standard entry fee for Low track players."],
        ["High Roller Multiplier: How many times the base buy-in High track players pay (default 4x)."],
        ["Bounty Cost: Additional fee per player that goes into the bounty pool."],
        ["Top-Off Multiplier: Fraction of buy-in for the optional break top-off (default 0.5x)."],
        ["Max Rebuys: Maximum number of rebuys allowed per player."],
        ["Rake Percent: House rake percentage (0 for home games)."],
    ]

    # ── Batch update all data ──
    batch_data = [
        {"range": "Settings!A1:H19", "values": settings_data},
        {"range": "Registration!A1:I31", "values": reg_rows},
        {"range": "Dashboard!A1:D27", "values": dashboard_data},
        {"range": "Instructions!A1:A40", "values": instructions_data},
    ]

    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=ss_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": batch_data,
        },
    ).execute()

    # ── Formatting requests ──
    requests = []

    # --- Freeze row 1 on Registration ---
    requests.append({
        "updateSheetProperties": {
            "properties": {"sheetId": 1, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # --- Bold headers ---
    # Settings row 1
    requests.append(bold_row(0, 0, 0, 8))
    # Settings payout header row 14 (0-indexed: 13)
    requests.append(bold_row(0, 13, 0, 8))
    # Registration row 1
    requests.append(bold_row(1, 0, 0, 9))
    # Dashboard row 1
    requests.append(bold_row(2, 0, 0, 4))
    # Dashboard "Main Pot" header row 15 (0-indexed: 14)
    requests.append(bold_row(2, 14, 0, 4))
    # Dashboard "Side Pot" header row 22 (0-indexed: 21)
    requests.append(bold_row(2, 21, 0, 4))
    # Dashboard stat labels (rows 3-13, col A)
    for r in range(2, 13):
        requests.append(bold_row(2, r, 0, 1))
    # Instructions title
    requests.append(bold_row(3, 0, 0, 1))
    # Instructions section headers
    for r in [2, 6, 16, 21, 25, 29]:
        requests.append(bold_row(3, r, 0, 1))

    # --- Currency format on dollar columns ---
    currency_fmt = {"type": "NUMBER", "pattern": "$#,##0.00"}

    # Settings B2 (Base Buy-In value)
    requests.append(number_format(0, 1, 3, 1, 2, currency_fmt))
    # Settings B4 (Bounty Cost)
    requests.append(number_format(0, 3, 4, 1, 2, currency_fmt))
    # Settings C2:C7 (calculated dollar values)
    requests.append(number_format(0, 1, 7, 2, 3, currency_fmt))

    # Registration F-I columns (cols 5-8), rows 2-31 (1-30 0-indexed)
    requests.append(number_format(1, 1, 31, 5, 9, currency_fmt))

    # Dashboard B column for dollar values (rows 7-13, 0-indexed 6-12)
    requests.append(number_format(2, 6, 13, 1, 2, currency_fmt))
    # Dashboard D column for payout amounts (rows 16-20 and 23-27)
    requests.append(number_format(2, 15, 20, 3, 4, currency_fmt))
    requests.append(number_format(2, 22, 27, 3, 4, currency_fmt))

    # --- Gray background on Settings calculated cells (C2:C7) ---
    requests.append({
        "repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 1, "endRowIndex": 7, "startColumnIndex": 2, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })
    # Also gray on D column labels
    requests.append({
        "repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 1, "endRowIndex": 7, "startColumnIndex": 3, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # --- Data validation: Track dropdown (Low, High) on Registration B2:B31 ---
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": 1, "startRowIndex": 1, "endRowIndex": 31, "startColumnIndex": 1, "endColumnIndex": 2},
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": "Low"}, {"userEnteredValue": "High"}],
                },
                "showCustomUi": True,
                "strict": True,
            },
        }
    })

    # --- Checkboxes on Registration C (Buy-in Paid) and E (Top-Off) ---
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": 1, "startRowIndex": 1, "endRowIndex": 31, "startColumnIndex": 2, "endColumnIndex": 3},
            "rule": {"condition": {"type": "BOOLEAN"}},
        }
    })
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": 1, "startRowIndex": 1, "endRowIndex": 31, "startColumnIndex": 4, "endColumnIndex": 5},
            "rule": {"condition": {"type": "BOOLEAN"}},
        }
    })

    # --- Data validation: Rebuy Count 0-2 on Registration D2:D31 ---
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": 1, "startRowIndex": 1, "endRowIndex": 31, "startColumnIndex": 3, "endColumnIndex": 4},
            "rule": {
                "condition": {
                    "type": "NUMBER_BETWEEN",
                    "values": [{"userEnteredValue": "0"}, {"userEnteredValue": "2"}],
                },
                "strict": True,
            },
        }
    })

    # --- Conditional formatting: Low=blue, High=gold on Registration ---
    # Blue for Low track
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": 1, "startRowIndex": 1, "endRowIndex": 31, "startColumnIndex": 0, "endColumnIndex": 9}],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": '=$B2="Low"'}],
                    },
                    "format": {"backgroundColor": {"red": 0.85, "green": 0.92, "blue": 1.0}},
                },
            },
            "index": 0,
        }
    })
    # Gold for High track
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": 1, "startRowIndex": 1, "endRowIndex": 31, "startColumnIndex": 0, "endColumnIndex": 9}],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": '=$B2="High"'}],
                    },
                    "format": {"backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}},
                },
            },
            "index": 1,
        }
    })

    # --- Column widths ---
    # Registration col A wider
    requests.append(col_width(1, 0, 1, 180))
    # Dashboard col A wider
    requests.append(col_width(2, 0, 1, 300))
    # Instructions col A wider
    requests.append(col_width(3, 0, 1, 700))
    # Settings col A wider
    requests.append(col_width(0, 0, 1, 200))
    requests.append(col_width(0, 3, 4, 180))

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=ss_id,
        body={"requests": requests},
    ).execute()

    print("Sheet created successfully!")
    return url, ss_id


def bold_row(sheet_id, row, start_col, end_col):
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row,
                "endRowIndex": row + 1,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    }


def number_format(sheet_id, start_row, end_row, start_col, end_col, fmt):
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "cell": {"userEnteredFormat": {"numberFormat": fmt}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def col_width(sheet_id, start, end, px):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": start,
                "endIndex": end,
            },
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


if __name__ == "__main__":
    url, _ = main()

#!/usr/bin/env python3
"""
Update the Blinds Timer tab in the existing Poker Tournament Manager sheet.
Replaces the stub with a full blinds schedule table.
"""

import json
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
SPREADSHEET_ID = "1K0A9KhfQ_eHCVOKJ76xhjjCke_kJVTJj89SeWobNtcI"
CREDENTIALS_PATH = "/Users/sophie.arborbot/.openclaw/workspace/arborfam-hub-token.json"
TAB_NAME = "⏱ Blinds Timer (stub)"
NEW_TAB_NAME = "⏱ Blinds Timer"
SID_BLINDS = 2125834582

# Colors
WHITE = {"red": 1, "green": 1, "blue": 1}
DARK_HEADER = {"red": 0.15, "green": 0.15, "blue": 0.3}
ORANGE_BREAK = {"red": 1.0, "green": 0.8, "blue": 0.4}
LIGHT_ROW = {"red": 0.95, "green": 0.95, "blue": 1.0}
WHITE_BG = {"red": 1, "green": 1, "blue": 1}
SETTINGS_BG = {"red": 0.93, "green": 0.96, "blue": 1.0}


def authorize():
    with open(CREDENTIALS_PATH) as f:
        token_data = json.load(f)
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


def build_blinds_rows():
    """Build the full blinds timer data."""
    rows = []

    # Rows 0-3: Settings section
    rows.append(["⏱ BLINDS TIMER", "", "", "", "", ""])  # row 0 (A1)
    rows.append(["Starting Stack:", "10,000", "", "Ante starts at level:", 5, ""])  # row 1
    rows.append(["Level duration default:", "20 min", "", "", "", ""])  # row 2
    rows.append(["💡 Highlight the current row manually as you progress", "", "", "", "", ""])  # row 3

    # Row 4: blank
    rows.append([])

    # Row 5: Header
    rows.append(["Level", "Small Blind", "Big Blind", "Ante", "Duration (min)", "Total Time Elapsed"])

    # Blind structure data: (level_label, sb, bb, duration_min, is_break, break_note)
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

    # Data rows start at row 6 (1-indexed: row 7)
    data_start_row = 7  # 1-indexed row number for first data row
    for i, (level, sb, bb, duration, is_break, note) in enumerate(schedule):
        row_1idx = data_start_row + i  # 1-indexed row
        if is_break:
            # Elapsed time: sum of all durations above this row + this row's duration
            if i == 0:
                elapsed = f"=E{row_1idx}"
            else:
                elapsed = f"=F{row_1idx - 1}+E{row_1idx}"
            rows.append([note, "", "", "", duration, elapsed])
        else:
            # Ante: "Yes" if level number >= ante start level (B2 = row 2, col B = ante level)
            level_num = int(level)
            ante_formula = f'=IF({level_num}>=$E$2,"Yes","")'
            if i == 0:
                elapsed = f"=E{row_1idx}"
            else:
                elapsed = f"=F{row_1idx - 1}+E{row_1idx}"
            rows.append([f"Level {level}", sb, bb, ante_formula, duration, elapsed])

    return rows


def clear_and_write(service):
    """Clear old data and write new blinds timer data."""
    # Clear the entire tab
    service.spreadsheets().values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{TAB_NAME}'!A1:Z100",
    ).execute()

    rows = build_blinds_rows()
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{TAB_NAME}'!A1:F{len(rows)}",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()
    print(f"Wrote {len(rows)} rows of data.")
    return len(rows)


def build_format_requests(num_rows):
    """Build formatting requests for the blinds timer tab."""
    requests = []

    # First, unprotect (we'll handle protection separately)

    # Column widths
    col_widths = [
        (0, 200),  # A: Level
        (1, 120),  # B: Small Blind
        (2, 120),  # C: Big Blind
        (3, 80),   # D: Ante
        (4, 140),  # E: Duration
        (5, 180),  # F: Total Time Elapsed
    ]
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

    # Set all text to 14pt minimum
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 0, "endRowIndex": num_rows},
            "cell": {"userEnteredFormat": {"textFormat": {"fontSize": 14}}},
            "fields": "userEnteredFormat.textFormat.fontSize",
        }
    })

    # Row 0 (title): bold, 18pt
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 0, "endRowIndex": 1,
                       "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 18}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # Rows 1-2 (settings): bold labels, light background
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

    # Row 3 (instruction note): italic
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 3, "endRowIndex": 4,
                       "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"textFormat": {"italic": True, "fontSize": 12}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # Row 5 (header): dark background, white bold text, 14pt
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": 5, "endRowIndex": 6,
                       "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {
                "backgroundColor": DARK_HEADER,
                "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": WHITE},
                "horizontalAlignment": "CENTER",
            }},
            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat,userEnteredFormat.horizontalAlignment",
        }
    })

    # Data rows (row 6 onward): alternating shading + break highlighting
    # Schedule order: L1, L2, L3, L4, BREAK, L5, L6, L7, L8, BREAK, L9, L10, L11, L12, L13
    break_indices = [4, 9]  # 0-based offset within data rows
    data_start = 6  # 0-indexed row of first data row

    for i in range(15):  # 15 data rows
        row_idx = data_start + i
        if i in break_indices:
            # Break row: orange background, bold
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": SID_BLINDS, "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                               "startColumnIndex": 0, "endColumnIndex": 6},
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": ORANGE_BREAK,
                        "textFormat": {"bold": True, "fontSize": 14},
                        "horizontalAlignment": "CENTER",
                    }},
                    "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat,userEnteredFormat.horizontalAlignment",
                }
            })
        else:
            # Alternating rows
            # Count non-break rows before this one to determine even/odd
            non_break_count = i - sum(1 for b in break_indices if b < i)
            bg = LIGHT_ROW if non_break_count % 2 == 0 else WHITE_BG
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": SID_BLINDS, "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                               "startColumnIndex": 0, "endColumnIndex": 6},
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": bg,
                        "horizontalAlignment": "CENTER",
                    }},
                    "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment",
                }
            })

    # Center-align the level column for all data rows
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": data_start, "endRowIndex": data_start + 15,
                       "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT"}},
            "fields": "userEnteredFormat.horizontalAlignment",
        }
    })

    # Number format for blind columns (B, C) — no decimals
    requests.append({
        "repeatCell": {
            "range": {"sheetId": SID_BLINDS, "startRowIndex": data_start, "endRowIndex": data_start + 15,
                       "startColumnIndex": 1, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Freeze header rows (rows 0-5)
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


def remove_protection(service):
    """Remove any existing protection on the Blinds Timer tab."""
    sheet_meta = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        fields="sheets.properties,sheets.protectedRanges",
    ).execute()

    for sheet in sheet_meta.get("sheets", []):
        if sheet["properties"]["sheetId"] == SID_BLINDS:
            for pr in sheet.get("protectedRanges", []):
                requests = [{"deleteProtectedRange": {"protectedRangeId": pr["protectedRangeId"]}}]
                service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": requests},
                ).execute()
                print(f"Removed protection: {pr['protectedRangeId']}")
            break


def add_warning_protection(service):
    """Re-protect with warningOnly=True."""
    requests = [{
        "addProtectedRange": {
            "protectedRange": {
                "range": {"sheetId": SID_BLINDS},
                "description": "Blinds Timer — edit with caution",
                "warningOnly": True,
            }
        }
    }]
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests},
    ).execute()
    print("Added warning-only protection.")


def main():
    print("Authorizing...")
    service = authorize()

    print("Removing old protection...")
    remove_protection(service)

    print("Writing blinds timer data...")
    num_rows = clear_and_write(service)

    print("Applying formatting...")
    requests = build_format_requests(num_rows)
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests},
    ).execute()

    print("Adding warning-only protection...")
    add_warning_protection(service)

    print("Done! Blinds Timer tab is live.")


if __name__ == "__main__":
    main()

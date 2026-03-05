# Poker Blinds Timer — Setup Guide

## Step 1: Open Apps Script

1. Open the poker spreadsheet
2. Go to **Extensions → Apps Script**

## Step 2: Add the script code

1. In the Apps Script editor, you'll see a file called `Code.gs`
2. **Delete** all existing code in `Code.gs`
3. Open `apps-script/blinds_timer.gs` from this repo and **copy the entire contents**
4. **Paste** it into `Code.gs`

## Step 3: Add the HTML dialog

1. In the Apps Script editor, click the **+** next to "Files" in the left sidebar
2. Select **HTML**
3. Name the file **TimerDialog** (exactly — no extension needed, the editor adds `.html`)
4. Delete any default content
5. Open `apps-script/timer_dialog.html` from this repo and **copy the entire contents**
6. **Paste** it into `TimerDialog.html`

## Step 4: Authorize

1. Click **Save** (Ctrl+S / Cmd+S)
2. In the function dropdown (top bar), select **initializeTimer**
3. Click **Run**
4. A permissions dialog will appear — click **Review Permissions**
5. Choose your Google account
6. Click **Advanced → Go to [project name] (unsafe)** (this is normal for custom scripts)
7. Click **Allow**

## Step 5: Use the timer

1. Go back to the spreadsheet and **reload the page**
2. The **🃏 Poker Timer** menu will appear in the menu bar
3. Click **🃏 Poker Timer → ▶ Start Timer**
4. A large timer dialog opens — visible to the whole room on a shared screen

## Timer Controls

| Button | Action |
|--------|--------|
| **Pause** / **Resume** | Toggle the countdown |
| **Next Level** | Advance to the next blind level |
| **Snooze 2min** | Appears when time expires — adds 2 minutes |

The timer reads the blind schedule directly from the **⏱ Blinds Timer** sheet tab. Edit the schedule there and the timer picks up changes on next start.

## Menu items

- **▶ Start Timer** — Opens the timer dialog starting at Level 1
- **⏸ Pause / Resume** — Toggles pause from the menu (also works from the dialog button)
- **⏭ Next Level** — Skips to the next level
- **🔄 Reset Timer** — Resets everything back to Level 1

## When time expires

The dialog **flashes black and white** until you click **Next Level** or **Snooze 2min**.

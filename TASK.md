# Poker Tournament Manager — Build Task

## Goal
1. Create GitHub repo `sagearbor/neighborhood-poker` (public)
2. Create a live Google Sheet in Sage's Drive via Sheets API
3. Commit README.md and one_pager_pitch.md to the repo
4. Report final Sheet URL and repo URL

## Credentials
- Google token: /Users/sophie.arborbot/.openclaw/workspace/arborfam-hub-token.json
- Google credentials: /Users/sophie.arborbot/.openclaw/workspace/arborfam-hub-credentials.json
- GitHub: `gh` CLI authenticated as sagearbor

## Google Sheet Structure

### Tab 1: Settings
Named input cells (B column, label in A column):
- Base_BuyIn: $40
- High_Roller_Multiplier: 4
- Bounty_Cost: $10
- TopOff_Multiplier: 0.5
- Max_Rebuys: 2
- Rake_Percent: 0

Calculated read-only cells (C column, labeled):
- High_Total_BuyIn = Base_BuyIn * High_Roller_Multiplier
- Side_Pot_Per_Person = Base_BuyIn * (High_Roller_Multiplier - 1)
- Low_TopOff = Base_BuyIn * TopOff_Multiplier
- High_TopOff = High_Total_BuyIn * TopOff_Multiplier
- Low_Total_Entry = Base_BuyIn + Bounty_Cost
- High_Total_Entry = High_Total_BuyIn + Bounty_Cost

Payout thresholds table (rows 15+):
Headers: Min Players | Max Players | Places Paid | 1st% | 2nd% | 3rd% | 4th% | 5th%
Data:
2 | 4 | 1 | 100 | 0 | 0 | 0 | 0
5 | 8 | 2 | 65 | 35 | 0 | 0 | 0
9 | 15 | 3 | 50 | 30 | 20 | 0 | 0
16 | 25 | 4 | 45 | 27 | 17 | 11 | 0
26 | 999 | 5 | 40 | 25 | 16 | 11 | 8

### Tab 2: Registration
Columns A-I, row 1 = headers, rows 2-31 = player slots:
A: Player Name
B: Track (data validation dropdown: Low, High)
C: Buy-in Paid? (checkbox)
D: Rebuy Count (data validation: 0 to 2, or use number input)
E: Top-Off? (checkbox)
F: Total Cash Collected (formula)
G: Main Pot Contribution (formula, can hide column)
H: Side Pot Contribution (formula, can hide column)
I: Bounty Contribution (formula, can hide column)

Formula logic for row 2 (reference Settings by row number since named ranges need script):
Assume Settings tab has:
- B2 = Base_BuyIn
- B3 = High_Roller_Multiplier  
- B4 = Bounty_Cost
- B5 = TopOff_Multiplier
- B6 = Max_Rebuys
- B7 = Rake_Percent
Calculated:
- C2 = High_Total_BuyIn
- C3 = Side_Pot_Per_Person
- C4 = Low_TopOff
- C5 = High_TopOff
- C6 = Low_Total_Entry
- C7 = High_Total_Entry

Registration formulas (row 2):
- F2 (Total Cash): =IF(C2,IF(B2="High",Settings!$C$7,Settings!$C$6),0) + D2*IF(B2="High",Settings!$C$7,Settings!$C$6) + IF(E2,IF(B2="High",Settings!$C$5,Settings!$C$4),0)
- G2 (Main Pot): =IF(C2,Settings!$B$2,0) + D2*Settings!$B$2 + IF(E2,Settings!$C$4,0)
- H2 (Side Pot): =IF(B2="High",IF(C2,Settings!$C$3,0)+D2*Settings!$C$3+IF(E2,Settings!$C$5-Settings!$C$4,0),0)
- I2 (Bounty): =IF(C2,Settings!$B$4,0)+D2*Settings!$B$4

### Tab 3: Dashboard
Display cells:
- Total Players: =COUNTIF(Registration!B2:B31,"Low")+COUNTIF(Registration!B2:B31,"High")
- Low Track Count: =COUNTIF(Registration!B2:B31,"Low")
- High (Whale) Track Count: =COUNTIF(Registration!B2:B31,"High")
- Total Cash in Box: =SUM(Registration!F2:F31)
- Bounty Pool: =SUM(Registration!I2:I31)
- Gross Prize Pool: =SUM(Registration!G2:G31)+SUM(Registration!H2:H31)
- Rake Amount: =Gross_Prize_Pool * Settings!B7/100
- Net Prize Pool: =Gross_Prize_Pool - Rake_Amount
- Main Pot Total: =SUM(Registration!G2:G31)*(1-Settings!$B$7/100)
- Side Pot Total: =SUM(Registration!H2:H31)*(1-Settings!$B$7/100)

Two payout tables using IFS/VLOOKUP against Settings payout table:
For each table, look up the player count in the payout thresholds to get places paid and percentages.
Main Pot table uses total player count. Side Pot table uses only High track count.
Show dollar amounts for each place. Label Side Pot table "HIGH ROLLER SIDE POT — Whales Only"

### Tab 4: Instructions
Static text explaining how to use the sheet, duplicate for new quarter, share safely.

## Formatting
- Freeze row 1 on Registration tab
- Bold all headers
- Color Low track rows blue (light), High track rows gold (light) — use conditional formatting on B column in Registration
- Currency format on all dollar columns
- Settings tab: gray background on calculated cells (read-only visual cue)

## GitHub Repo Files

### README.md
- What this is
- Link to make a copy of the Google Sheet (use the actual sheet URL)  
- Tournament night step-by-step
- How to start a new quarter (duplicate Registration tab)
- Settings reference

### one_pager_pitch.md
Persuasive 1-pager for co-organizers:
- The problem: $180 scares casuals, $40 bores sharks
- The solution: "Pro-Am Concurrent Flight" tournament
- How it works: same starting chip stack, two separate prize pools
- Example math: 10 low players ($40 each) + 4 whales ($160 each) = $400 main pot + $480 side pot
- Why it's fair: chip stacks are equal, whales pay extra for access to side pot only

## Steps
1. Write the Python script to create the Google Sheet with all tabs, formulas, formatting
2. Run it — capture the Sheet URL
3. Create GitHub repo: `gh repo create sagearbor/neighborhood-poker --public --description "Pro-Am poker tournament manager"`
4. Write README.md and one_pager_pitch.md (include actual sheet URL in README)
5. Commit and push
6. Print final Sheet URL and repo URL

When completely finished, run:
~/.openclaw/bin/openclaw system event --text "Poker sheet done! Sheet URL: <url> | Repo: https://github.com/sagearbor/neighborhood-poker" --mode now

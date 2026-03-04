# Neighborhood Poker — Pro-Am Tournament Manager

A Google Sheets-based tournament manager for **"Pro-Am Concurrent Flight"** poker nights. Low-stakes players ($40) and high-rollers ($160) play the same game with equal chip stacks, but compete for separate prize pools.

## Get the Sheet

**[Make a copy of the Tournament Manager](https://docs.google.com/spreadsheets/d/1RGW8Va04U1NLA9c2GiKcN35st5FgltS_n-2Q8E_r5Cw/copy)**

Or view it here: [Poker Tournament Manager — Q2 2026](https://docs.google.com/spreadsheets/d/1RGW8Va04U1NLA9c2GiKcN35st5FgltS_n-2Q8E_r5Cw/edit)

## Tournament Night — Step by Step

1. **Open the Registration tab** before players arrive.
2. **Add each player's name** in column A.
3. **Select their track** — Low ($40) or High ($160) — from the dropdown in column B.
4. **Check "Buy-in Paid?"** when they hand you cash.
5. **Rebuys** — increment the Rebuy Count (max 2) if a player buys back in.
6. **Top-offs** — check the Top-Off box during the break if a player adds chips.
7. **Check the Dashboard tab** for live totals — prize pools, payout amounts, and bounty pool.
8. **Pay out** using the Dashboard payout tables:
   - Main Pot: all players eligible
   - Side Pot: High track ("Whales") only
   - Bounties: $10 per knockout from the bounty pool

## Starting a New Quarter

1. Right-click the **Registration** tab → **Duplicate**.
2. Rename the duplicate (e.g., "Registration Q3 2026").
3. Clear all player data from the active Registration tab.
4. The Dashboard automatically recalculates from the active Registration tab.

## Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| Base Buy-In | $40 | Standard entry for Low track |
| High Roller Multiplier | 4x | High track pays this × base ($160) |
| Bounty Cost | $10 | Per-player fee for bounty pool |
| Top-Off Multiplier | 0.5x | Break top-off as fraction of buy-in |
| Max Rebuys | 2 | Maximum rebuys per player |
| Rake Percent | 0% | House rake (0 for home games) |

## How It Works

Everyone starts with the same chip stack. Low track players buy in for $40; High track "whales" buy in for $160 (4× the base). The extra $120 per whale goes into a separate **Side Pot** that only whales compete for. The base $40 from every player goes into the **Main Pot** that everyone competes for.

Fair for casuals. Exciting for sharks. One table.

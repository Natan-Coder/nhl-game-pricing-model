#!/usr/bin/env python3
"""Explore totals market viability"""

from dotenv import load_dotenv
import psycopg
import os
import numpy as np

load_dotenv()
conn = psycopg.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

# Get all completed games with totals lines
cur.execute('''
    SELECT
        gr.game_id
        ,gr.home_goals + gr.away_goals as actual_total
        ,oq.line_number / 100.0 as line_value
        ,oq.american_odds
    FROM game_results gr
    JOIN odds_quotes oq ON gr.game_id = oq.game_id
    WHERE oq.market = 'total'
      AND oq.outcome = 'over'  -- Filtering for total value (e.g. '7.5')
      AND oq.book = 'DraftKings'
    LIMIT 100
''')

rows = cur.fetchall()
print(f"Found {len(rows)} games with totals data")
print()

if len(rows) == 0:
    print("No data found. Check if odds_quotes has totals data.")
    conn.close()
    exit()
    
actual_totals = [row[1] for row in rows]  # home_goals + away_goals
line_values = [float(row[2]) for row in rows]  # bookmaker odds (e.g., 6.5)

print("=" * 80)
print("TOTALS MARKET ANALYSIS")
print("=" * 80)
print()

print(f"Sample size: {len(actual_totals)} games")
print(f"Average actual total: {np.mean(actual_totals):.2f} goals")
print(f"Std dev: {np.std(actual_totals):.2f} goals")
print(f"Min: {np.min(actual_totals):.2f} goals")  # Shows "3.00"
print(f"Max: {np.max(actual_totals):.2f} goals")  # Shows "12.00"
print()

print(f"Average bookmaker line: {np.mean(line_values):.2f}")
print(f"Line range: {np.min(line_values):.2f} to {np.max(line_values):.2f}")
print()

# How often does the over hit?
overs = sum(1 for i in range(len(rows)) if actual_totals[i] > line_values[i])
unders = sum(1 for i in range(len(rows)) if actual_totals[i] < line_values[i])
pushes = sum(1 for i in range(len(rows)) if actual_totals[i] == line_values[i])

print("Over/Under Results:")
print(f"  Overs:  {overs} ({overs/len(rows)*100:.1f}%)")
print(f"  Unders: {unders} ({unders/len(rows)*100:.1f}%)")
print(f"  Pushes: {pushes} ({pushes/len(rows)*100:.1f}%)")
print()

# Do the bookmakers know their stuff (Well-calibrated?)
if abs(overs/len(rows) - 0.5) < 0.05:
    print("Bookmakers are well-calibrated (close to 50/50)")
else:
    print("Imbalance detected! Could be an opportunity")
    
print("-" * 80)
print("Sample games:")
print(f"{'game_id':<12} | {'actual':<6} | {'line':<6} | {'result':<8} | {'odds'}")
print("-" * 80)
for i in range(min(10, len(rows))):
    game_id, actual, line, odds = rows[i]
    result = 'OVER' if actual > float(line) else ('UNDER' if actual < float(line) else 'PUSH')
    print(f"{game_id:<12} | {actual:<6.1f} | {line:<6} | {result:<8} | {odds}")
    
conn.close()
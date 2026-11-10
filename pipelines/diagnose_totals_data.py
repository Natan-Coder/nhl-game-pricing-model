#!/usr/bin/env python3
"""Diagnose why compute_totals_edges found 0 games"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print('Diagnostic: Why no totals edges?')
print('=' * 80)

# Check 1: Games with predictions
cur.execute("""
    SELECT COUNT(*)
    FROM game_pricing gp
    JOIN game_features gf ON gp.game_id = gf.game_id
    WHERE gp.predicted_total IS NOT NULL
      AND gf.game_date >= CURRENT_DATE
""")
count = cur.fetchone()[0]
print(f'1. Games with predicted_total and date >= today: {count}')

# Check 2: Games with totals odds
cur.execute("""
    SELECT COUNT(DISTINCT game_id)
    FROM odds_quotes
    WHERE market = 'total'
      AND outcome = 'over'
""")
count = cur.fetchone()[0]
print(f'2. Games with totals odds (over): {count}')

# Check 3: Games with BOTH
cur.execute("""
    SELECT COUNT(*)
    FROM game_pricing gp
    JOIN game_features gf ON gp.game_id = gf.game_id
    JOIN odds_quotes oq ON gp.game_id = oq.game_id
        AND oq.market = 'total'
        AND oq.outcome = 'over'
    WHERE gp.predicted_total IS NOT NULL
      AND gf.game_date >= CURRENT_DATE
""")
count = cur.fetchone()[0]
print(f'3. Games with BOTH prediction AND over odds: {count}')

# Check 4: Do we have matching under odds?
cur.execute("""
    SELECT COUNT(*)
    FROM game_pricing gp
    JOIN game_features gf ON gp.game_id = gf.game_id
    JOIN odds_quotes over_odds ON gp.game_id = over_odds.game_id
        AND over_odds.market = 'total'
        AND over_odds.outcome = 'over'
    JOIN odds_quotes under_odds ON gp.game_id = under_odds.game_id
        AND under_odds.market = 'total'
        AND under_odds.outcome = 'under'
        AND under_odds.book = over_odds.book
        AND under_odds.line_number = over_odds.line_number
    WHERE gp.predicted_total IS NOT NULL
      AND gf.game_date >= CURRENT_DATE
""")
count = cur.fetchone()[0]
print(f'4. Games with prediction + matching over/under pairs: {count}')

# Check 5: Sample of games with predictions
print('\nSample games with predictions:')
cur.execute("""
    SELECT gp.game_id, gf.game_date, gp.predicted_total
    FROM game_pricing gp
    JOIN game_features gf ON gp.game_id = gf.game_id
    WHERE gp.predicted_total IS NOT NULL
      AND gf.game_date >= CURRENT_DATE
    LIMIT 5
""")
for row in cur.fetchall():
    print(f'  {row[0]} on {row[1]}: predicted {row[2]:.2f}')

# Check 6: Sample of totals odds
print('\nSample totals odds:')
cur.execute("""
    SELECT game_id, book, market, outcome, line_number / 100.0, american_odds
    FROM odds_quotes
    WHERE market = 'total'
    LIMIT 10
""")
for row in cur.fetchall():
    print(f'  {row[0]} {row[1]}: {row[2]} {row[3]} {row[4]:.1f} @ {row[5]:+}')

conn.close()

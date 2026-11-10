#!/usr/bin/env python3
"""Check overlap between predictions and odds"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print('Games WITH predictions:')
print('=' * 80)
cur.execute("""
    SELECT gp.game_id, gf.game_date
    FROM game_pricing gp
    JOIN game_features gf ON gp.game_id = gf.game_id
    WHERE gp.predicted_total IS NOT NULL
      AND gf.game_date >= CURRENT_DATE
    ORDER BY gp.game_id
    LIMIT 10
""")
pred_games = {row[0]: row[1] for row in cur.fetchall()}
for gid, date in pred_games.items():
    print(f'  {gid} on {date}')

print()
print('Games WITH totals odds (2026 season):')
print('=' * 80)
cur.execute("""
    SELECT DISTINCT game_id
    FROM odds_quotes
    WHERE game_id::text LIKE '2026%'
      AND market = 'total'
    ORDER BY game_id
""")
odds_games = [row[0] for row in cur.fetchall()]
for gid in odds_games:
    print(f'  {gid}')

print()
print('OVERLAP (games with both):')
print('=' * 80)
overlap = set(pred_games.keys()) & set(odds_games)
if len(overlap) == 0:
    print('  None! This is why compute_totals_edges found 0 games.')
    print()
    print('Reason: Predictions start at game', min(pred_games.keys()))
    print('        Odds end at game', max(odds_games))
else:
    for gid in sorted(overlap):
        print(f'  {gid} on {pred_games[gid]}')

conn.close()

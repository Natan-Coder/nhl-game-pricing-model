#!/usr/bin/env python3
"""Check predicted totals vs bookmaker lines"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Get predictions with odds
cur.execute('''
    SELECT
        gp.game_id,
        gf.home_team,
        gf.away_team,
        gf.game_date,
        gp.predicted_total,
        oq.line_number / 100.0 as bookmaker_line,
        oq.book
    FROM game_pricing gp
    JOIN game_features gf ON gp.game_id = gf.game_id
    LEFT JOIN odds_quotes oq ON gp.game_id = oq.game_id
        AND oq.market = 'total'
        AND oq.outcome = 'over'
    WHERE gp.predicted_total IS NOT NULL
      AND gf.game_date >= CURRENT_DATE
    ORDER BY gf.game_date, gp.game_id
    LIMIT 20
''')

rows = cur.fetchall()
print(f'Predictions vs Bookmaker Lines')
print('=' * 100)
print(f'{"game_id":<12} | {"matchup":<20} | {"date":<12} | {"predicted":<10} | {"book line":<10} | {"diff":<6} | {"book"}')
print('-' * 100)

for row in rows:
    game_id, home, away, date, pred, line, book = row
    matchup = f'{away} @ {home}'
    pred_float = float(pred) if pred else 0
    line_float = float(line) if line else 0
    diff = f'{pred_float - line_float:.2f}' if line else 'N/A'
    line_str = f'{line_float:.1f}' if line else 'N/A'
    book_str = book if book else 'N/A'
    print(f'{game_id:<12} | {matchup:<20} | {str(date):<12} | {pred_float:<10.2f} | {line_str:<10} | {diff:<6} | {book_str}')

conn.close()

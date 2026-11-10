#!/usr/bin/env python3
"""Show tonight's totals lines"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Get tonight's totals
cur.execute('''
    SELECT
        oq.game_id,
        oq.book,
        oq.line_number / 100.0 as total_line,
        oq.american_odds as over_odds
    FROM odds_quotes oq
    WHERE oq.market = 'total'
      AND oq.outcome = 'over'
      AND oq.captured_at > NOW() - INTERVAL '2 hours'
    ORDER BY oq.game_id, oq.book
''')

rows = cur.fetchall()

print('Tonight\'s Totals Lines (Oct 15, 2026)')
print('=' * 80)
print(f'{"game_id":<12} | {"book":<15} | {"line":<6} | {"over odds":<10}')
print('-' * 80)

for row in rows:
    print(f'{row[0]:<12} | {row[1]:<15} | {row[2]:<6.1f} | {row[3]:<+10}')

print()
print('Historical baseline: 6.04 avg actual, 6.20 avg line, 56% unders')
print()
print('Simple strategy:')
print('  - If line > 6.2 → Consider betting UNDER')
print('  - If line < 5.9 → Consider betting OVER')

conn.close()

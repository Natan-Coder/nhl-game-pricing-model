#!/usr/bin/env python3
"""Check 2026 season odds availability"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print('2026 Season Odds Availability:')
print('=' * 80)

cur.execute("""
    SELECT market, COUNT(DISTINCT game_id) as games, MAX(captured_at) as last_fetch
    FROM odds_quotes
    WHERE game_id::text LIKE '2026%'
    GROUP BY market
    ORDER BY market
""")

rows = cur.fetchall()
if len(rows) == 0:
    print('No 2026 odds found!')
else:
    for row in rows:
        print(f'{row[0]:15} {row[1]:3} games, last fetched: {row[2]}')

print()
print('Specific games with totals odds:')
cur.execute("""
    SELECT DISTINCT game_id
    FROM odds_quotes
    WHERE game_id::text LIKE '2026%'
      AND market = 'total'
    ORDER BY game_id
    LIMIT 10
""")

rows = cur.fetchall()
if len(rows) == 0:
    print('  None found - need to run ingest_odds!')
else:
    for row in rows:
        print(f'  {row[0]}')

conn.close()

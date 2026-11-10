#!/usr/bin/env python3
"""Check what odds were recently fetched"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print('Recent odds by market (last hour):')
print('=' * 80)

# Check all markets fetched recently
cur.execute('''
    SELECT
        market,
        COUNT(DISTINCT game_id) as games,
        COUNT(*) as total_quotes,
        MAX(captured_at) as last_captured
    FROM odds_quotes
    WHERE captured_at > NOW() - INTERVAL '1 hour'
    GROUP BY market
    ORDER BY last_captured DESC
''')

for row in cur.fetchall():
    print(f'{row[0]:15} | {row[1]} games | {row[2]} quotes | Last: {row[3]}')

print()
print('Sample game_ids from recent odds:')
print('-' * 80)

cur.execute('''
    SELECT DISTINCT game_id
    FROM odds_quotes
    WHERE captured_at > NOW() - INTERVAL '1 hour'
    LIMIT 10
''')

for row in cur.fetchall():
    print(f'  {row[0]}')

print()
print('Checking if these games exist in game_results...')
print('-' * 80)

cur.execute('''
    SELECT
        COUNT(DISTINCT oq.game_id) as in_odds,
        COUNT(DISTINCT gr.game_id) as in_results
    FROM (
        SELECT DISTINCT game_id
        FROM odds_quotes
        WHERE captured_at > NOW() - INTERVAL '1 hour'
    ) oq
    LEFT JOIN game_results gr ON oq.game_id = gr.game_id
''')

row = cur.fetchone()
print(f'Games in odds_quotes: {row[0]}')
print(f'Games also in game_results: {row[1]}')

if row[0] > row[1]:
    print()
    print('⚠️  Some games have odds but not results yet (future games)')

conn.close()

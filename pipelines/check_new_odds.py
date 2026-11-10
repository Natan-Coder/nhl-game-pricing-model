#!/usr/bin/env python3
"""Check what odds were just fetched"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Check what we just fetched
cur.execute('''
    SELECT
        SUBSTRING(oq.game_id::text FROM 1 FOR 4) as season,
        COUNT(DISTINCT oq.game_id) as games,
        MIN(gr.game_date) as first_game,
        MAX(gr.game_date) as last_game
    FROM odds_quotes oq
    JOIN game_results gr ON oq.game_id = gr.game_id
    WHERE oq.market = 'total'
      AND oq.captured_at > NOW() - INTERVAL '5 minutes'
    GROUP BY SUBSTRING(oq.game_id::text FROM 1 FOR 4)
    ORDER BY season DESC
''')

print('Just fetched totals odds for:')
for row in cur.fetchall():
    print(f'  Season {row[0]}: {row[1]} games ({row[2]} to {row[3]})')

conn.close()

#!/usr/bin/env python3
"""Check game_edges table schema"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'edges'
    ORDER BY ordinal_position
""")

print('edges schema:')
print('=' * 80)
print(f'{"Column Name":<30} {"Data Type":<20} {"Nullable"}')
print('-' * 80)

for row in cur.fetchall():
    print(f'{row[0]:<30} {row[1]:<20} {row[2]}')

# Also check constraints/unique keys
print('\nConstraints:')
print('-' * 80)
cur.execute("""
    SELECT constraint_name, constraint_type
    FROM information_schema.table_constraints
    WHERE table_name = 'edges'
""")

for row in cur.fetchall():
    print(f'{row[0]:<50} {row[1]}')

conn.close()

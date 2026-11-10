import psycopg
from pipelines.config import DATABASE_URL
from decimal import Decimal

conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()

# Get COL and LAK ELOs
cur.execute("""
    SELECT DISTINCT ON (team_abbr) team_abbr, elo
    FROM team_elos
    WHERE team_abbr IN ('COL', 'LAK')
    ORDER BY team_abbr, updated_at DESC
""")

elos = cur.fetchall()
for team, elo in elos:
    print(f'{team}: {float(elo):.1f}')

col_elo = next((float(elo) for team, elo in elos if team == 'COL'), 1500)
lak_elo = next((float(elo) for team, elo in elos if team == 'LAK'), 1500)

# Calculate raw ELO probability
elo_diff = (col_elo + 50 - lak_elo) / 400
raw_prob_home = 10**elo_diff / (1 + 10**elo_diff)

print(f'\nRaw ELO prediction: COL {raw_prob_home*100:.1f}%, LAK {(1-raw_prob_home)*100:.1f}%')
print(f'Market odds: LAK +225 = {100/(225+100)*100:.1f}%')
print(f'Edge: {(1-raw_prob_home)*100 - 100/(225+100)*100:.1f}%')

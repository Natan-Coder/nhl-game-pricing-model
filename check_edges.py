import psycopg
from pipelines.config import DATABASE_URL

conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()

# Get COL vs LAK game_id
cur.execute("SELECT game_id FROM game_features WHERE home_team='COL' AND away_team='LAK' AND game_date >= '2026-04-21' ORDER BY game_date LIMIT 1")
game_id = cur.fetchone()[0]

print(f"Game ID: {game_id}")
print()

# Check edges for LAK (away) bets
cur.execute("""
    SELECT e.book, e.outcome, e.model_prob, e.american_odds, e.edge
    FROM edges e
    WHERE e.game_id = %s
      AND e.market = 'moneyline'
      AND e.outcome = 'away'
    LIMIT 5
""", (game_id,))

print("edges table (LAK bets):")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} @ {row[3]}, model={float(row[2])*100:.1f}%, edge={float(row[4])*100:.1f}%")

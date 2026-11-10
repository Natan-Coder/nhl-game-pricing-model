import psycopg
from pipelines.config import DATABASE_URL

conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()

# Check team_ratings table
cur.execute("SELECT team_abbr, elo, updated_at FROM team_ratings WHERE team_abbr IN ('COL', 'LAK') ORDER BY team_abbr")
print("team_ratings table:")
for row in cur.fetchall():
    print(f"  {row[0]}: ELO={float(row[1]):.1f}, updated={row[2]}")

print()

# Check all teams
cur.execute("SELECT COUNT(*), AVG(elo), MIN(elo), MAX(elo) FROM team_ratings")
row = cur.fetchone()
print(f"All teams: {row[0]} teams, avg ELO={float(row[1]):.1f}, range={float(row[2]):.1f}-{float(row[3]):.1f}")

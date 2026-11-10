import sys
sys.path.append('.')
from pipelines.config import DATABASE_URL
import psycopg
from datetime import datetime

conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()

# Check bet #441
cur.execute("SELECT bet_id, game_date, home_team, away_team, bet_team, bet_type, odds, stake, bet_status FROM bet_log WHERE bet_id = 441")
row = cur.fetchone()

if row:
    print("=== BET #441 DETAILS ===")
    print(f"Game Date: {row[1]}")
    print(f"Matchup: {row[3]} @ {row[2]}")
    print(f"Bet Team: {row[4]}")
    print(f"Bet Type: {row[5]}")
    print(f"Odds: {row[6]}")
    print(f"Stake: ${row[7]}")
    print(f"Status: {row[8]}")
    print()

    # Check if game has results
    cur.execute("SELECT home_goals, away_goals FROM game_results WHERE game_date = %s AND home_team = %s AND away_team = %s",
                (row[1], row[2], row[3]))
    game_result = cur.fetchone()

    if game_result:
        print(f"GAME FINISHED: {row[3]} {game_result[1]} - {row[2]} {game_result[0]}")
    else:
        print("GAME NOT YET FINISHED (or not in database)")

        # Check upcoming games
        print("\n=== UPCOMING BUF GAMES ===")
        cur.execute("""
            SELECT gf.game_id, gf.game_date, gf.home_team, gf.away_team
            FROM game_features gf
            WHERE gf.game_date >= CURRENT_DATE
            AND (gf.home_team = 'BUF' OR gf.away_team = 'BUF')
            ORDER BY gf.game_date
            LIMIT 5
        """)
        upcoming = cur.fetchall()
        for g in upcoming:
            print(f"{g[1]}: {g[3]} @ {g[2]}")
else:
    print("Bet #441 not found")

conn.close()

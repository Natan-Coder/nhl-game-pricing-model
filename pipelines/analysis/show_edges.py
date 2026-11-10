# pipelines/analysis/show_edges.py
"""
Quick script to view today's actionable edges.
Usage: python -m pipelines.analysis.show_edges
"""
import psycopg
from pipelines.config import DATABASE_URL

def main():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    game_date,
                    away_team || ' @ ' || home_team as matchup,
                    market,
                    outcome,
                    american_odds,
                    edge,
                    kelly_fraction,
                    suggested_stake
                FROM actionable_edges
                ORDER BY edge DESC
                LIMIT 20
            """)
            
            print("\n" + "="*100)
            print("TODAY'S BEST EDGES")
            print("="*100)
            print(f"{'Date':<12} {'Matchup':<30} {'Market':<12} {'Bet':<10} {'Odds':<8} {'Edge':<8} {'Kelly':<8} {'Stake'}")
            print("="*100)
            
            for row in cur.fetchall():
                date, matchup, market, outcome, odds, edge, kelly, stake = row
                print(f"{str(date):<12} {matchup:<30} {market:<12} {outcome:<10} {odds:>6.0f} {edge:>6.2%} {kelly:>6.2%} ${float(stake):>7.2f}")
                
            print("="*100)
            
            # Summary stats
            cur.execute("SELECT COUNT(*), AVG(edge), MAX(edge) FROM actionable_edges")
            count, avg, max_edge = cur.fetchone()
            print(f"\nTotal actionable edges: {count}")
            print(f"Average edge: {avg:.2%}")
            print(f"Max edge: {max_edge:.2%}")

if __name__ == "__main__":
    main()
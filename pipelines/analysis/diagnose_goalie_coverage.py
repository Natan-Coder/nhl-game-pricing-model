# pipelines/analysis/diagnose_goalie_coverage.py
"""
Quick diagnostic to check goalie data coverage in game_features table.
"""
import psycopg
from pipelines.config import DATABASE_URL

with psycopg.connect(DATABASE_URL, sslmode="require") as conn:
    with conn.cursor() as cur:
        # Check overall coverage
        cur.execute("""
            SELECT
                COUNT(*) as total_games,
                COUNT(home_elo) as games_with_elo,
                COUNT(home_goalie_sv_pct) as games_with_sv_pct,
                COUNT(home_goalie_id) as games_with_goalie_id,
                COUNT(CASE WHEN home_elo IS NOT NULL AND home_goalie_sv_pct IS NOT NULL THEN 1 END) as games_with_both_elo_and_sv_pct
            FROM game_features
            WHERE game_date >= '2023-10-01'
        """)

        row = cur.fetchone()
        total, with_elo, with_sv_pct, with_goalie_id, with_both = row

        print("=" * 80)
        print("GOALIE DATA COVERAGE ANALYSIS")
        print("=" * 80)
        print(f"Total games (since 2023-10-01):     {total}")
        print(f"Games with ELO:                      {with_elo} ({with_elo/total*100:.1f}%)")
        print(f"Games with goalie save %:            {with_sv_pct} ({with_sv_pct/total*100:.1f}%)")
        print(f"Games with goalie ID:                {with_goalie_id} ({with_goalie_id/total*100:.1f}%)")
        print(f"Games with BOTH ELO and save %:      {with_both} ({with_both/total*100:.1f}%)")
        print("=" * 80)
        print()

        # Check what columns exist in game_features
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'game_features'
            AND column_name LIKE '%goalie%'
            ORDER BY ordinal_position
        """)

        print("GOALIE-RELATED COLUMNS IN game_features:")
        print("=" * 80)
        for col_name, data_type, nullable in cur.fetchall():
            print(f"  {col_name:30} {data_type:15} nullable={nullable}")
        print("=" * 80)
        print()

        # Sample a few rows to see what the data looks like
        cur.execute("""
            SELECT
                game_id,
                home_goalie_id,
                away_goalie_id,
                home_goalie_sv_pct,
                away_goalie_sv_pct
            FROM game_features
            WHERE game_date >= '2024-10-01'
            ORDER BY game_date DESC
            LIMIT 10
        """)

        print("SAMPLE DATA (10 most recent games from 2024-25 season):")
        print("=" * 80)
        print(f"{'game_id':<12} {'home_g_id':<12} {'away_g_id':<12} {'home_sv%':<12} {'away_sv%':<12}")
        print("-" * 80)
        for game_id, home_g_id, away_g_id, home_sv, away_sv in cur.fetchall():
            home_g_str = str(home_g_id) if home_g_id else "NULL"
            away_g_str = str(away_g_id) if away_g_id else "NULL"
            home_sv_str = f"{home_sv:.3f}" if home_sv else "NULL"
            away_sv_str = f"{away_sv:.3f}" if away_sv else "NULL"
            print(f"{game_id:<12} {home_g_str:<12} {away_g_str:<12} {home_sv_str:<12} {away_sv_str:<12}")
        print("=" * 80)

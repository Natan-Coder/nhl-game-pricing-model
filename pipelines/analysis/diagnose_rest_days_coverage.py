# pipelines/analysis/diagnose_rest_days_coverage.py
"""
Quick diagnostic to check rest days data coverage in game_features table.
"""
import psycopg
from pipelines.config import DATABASE_URL

with psycopg.connect(DATABASE_URL, sslmode="require") as conn:
    with conn.cursor() as cur:
        # Check what rest-related columns exist
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'game_features'
            AND column_name LIKE '%rest%'
            ORDER BY ordinal_position
        """)

        print("=" * 80)
        print("REST-RELATED COLUMNS IN game_features:")
        print("=" * 80)
        rest_columns = cur.fetchall()
        if not rest_columns:
            print("  No rest-related columns found!")
        else:
            for col_name, data_type, nullable in rest_columns:
                print(f"  {col_name:30} {data_type:15} nullable={nullable}")
        print("=" * 80)
        print()

        # If we found rest columns, check coverage
        if rest_columns:
            col_names = [row[0] for row in rest_columns]

            # Build dynamic query
            count_clauses = ", ".join([f"COUNT({col}) as {col}_count" for col in col_names])

            cur.execute(f"""
                SELECT
                    COUNT(*) as total_games,
                    {count_clauses}
                FROM game_features
                WHERE game_date >= '2023-10-01'
            """)

            row = cur.fetchone()
            total = row[0]

            print("REST DAYS DATA COVERAGE:")
            print("=" * 80)
            print(f"Total games (since 2023-10-01): {total}")
            for i, col in enumerate(col_names, start=1):
                count = row[i]
                pct = count / total * 100 if total > 0 else 0
                print(f"  {col:30} {count:6} ({pct:5.1f}%)")
            print("=" * 80)
            print()

            # Sample some data
            sample_cols = ", ".join(col_names)
            cur.execute(f"""
                SELECT game_id, game_date, home_team, away_team, {sample_cols}
                FROM game_features
                WHERE game_date >= '2024-10-01'
                ORDER BY game_date DESC
                LIMIT 5
            """)

            print("SAMPLE DATA (5 most recent games from current season):")
            print("=" * 80)
            for row in cur.fetchall():
                game_id, game_date, home, away = row[:4]
                rest_values = row[4:]
                print(f"Game: {game_id} on {game_date}")
                print(f"  {home} vs {away}")
                for col, val in zip(col_names, rest_values):
                    print(f"    {col}: {val}")
                print()
            print("=" * 80)

# pipelines/etl/create_missing_game_features.py
"""
Python file to create rows for the missing game features

"""
import logging
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)


def main():
    """Update game_features with missing games from game results."""
    
    log.info("=" * 80)
    log.info("UPDATING GAME FEATURES WITH MISSING GAMES")
    log.info("=" * 80)
    
    
    with psycopg.connect(
        DATABASE_URL,
        sslmode="require",
        prefer_query_mode=None,
        prepare_threshold=None,
        prepared_statement_cache_queries=None,
    ) as conn:
        with conn.cursor() as cur:
        
            cur.execute("""
            INSERT INTO game_features (game_id, game_date, home_team, away_team)
                SELECT gr.game_id, gr.game_date, gr.home_team, gr.away_team
                FROM game_results gr
                LEFT JOIN game_features gf ON gf.game_id = gr.game_id
                WHERE gf.game_id IS NULL
            """)
        
            rows_inserted = cur.rowcount
        
        conn.commit()
    
    log.info(f"Inserted {rows_inserted} new game_features rows")
    log.info("=" * 80)

if __name__ == "__main__":
    main()
    
    
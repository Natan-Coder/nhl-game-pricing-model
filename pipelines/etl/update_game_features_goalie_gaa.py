# pipelines/etl/update_game_features_goalie_gaa.py
"""
Update game_features table with gaa.

"""
from __future__ import annotations
import logging
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)


def main():
    """Update game_features with goals against average."""
    
    log.info("=" * 80)
    log.info("UPDATING GAME FEATURES WITH GOALIE AGAINST AVERAGE")
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
                UPDATE game_features gf
                SET
                    home_goalie_gaa = home_gs.gaa,
                    away_goalie_gaa = away_gs.gaa
                FROM game_goalies gg
                LEFT JOIN goalie_stats home_gs
                    ON home_gs.goalie_id = gg.home_goalie_id
                    AND home_gs.season = SUBSTRING(gg.game_id::text, 1, 4)::int
                LEFT JOIN goalie_stats away_gs
                    ON away_gs.goalie_id = gg.away_goalie_id
                    AND away_gs.season = SUBSTRING(gg.game_id::text, 1, 4)::int
                WHERE gf.game_id = gg.game_id
            """)
            
            rows_updated = cur.rowcount
        
        conn.commit()
    
    log.info("")
    log.info(f"Updated {rows_updated} games with goalie against average")
    log.info("=" * 80)


if __name__ == "__main__":
    main()
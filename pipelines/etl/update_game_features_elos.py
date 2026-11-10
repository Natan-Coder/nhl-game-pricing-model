# pipelines/etl/update_game_features_elos.py
"""
Update game_features table with home and away elos.

Joins team_elo_history to populate home_elo and away_elo columns in game_features.
"""
from __future__ import annotations
import logging
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)



def main():
    """Update game_features with home and away elos from team_elo_history."""
    
    log.info("=" * 80)
    log.info("UPDATING GAME FEATURES WITH ELO DATA")
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
                    home_elo = home_elo_hist.elo_rating,
                    away_elo = away_elo_hist.elo_rating
                FROM team_elo_history home_elo_hist
                JOIN team_elo_history away_elo_hist
                    ON home_elo_hist.game_id = away_elo_hist.game_id
                WHERE gf.game_id = home_elo_hist.game_id
                  AND home_elo_hist.team_code = gf.home_team
                  AND away_elo_hist.team_code = gf.away_team
            """)
            
            rows_updated = cur.rowcount
        
        conn.commit()
    
    log.info("")
    log.info(f"Updated {rows_updated} games with ELO data")
    log.info("=" * 80)

if __name__ == "__main__":
    main()
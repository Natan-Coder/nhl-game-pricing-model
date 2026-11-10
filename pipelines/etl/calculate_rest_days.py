# pipelines/etl/calculate_rest_days.py
"""
 Calculate rest days for each team before each game.
 Updates game_features table with home_rest and away_rest columns.
"""
from __future__ import annotations
import logging
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)


def main():
    """Calculate and update rest days for all games."""
    
    log.info("=" * 80)
    log.info("CALCULATING REST DAYS FOR ALL GAMES")
    log.info("Updating columns: home_rest, away_rest")
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
                UPDATE game_features current_game
                SET home_rest = (
                    -- home team's previous game
                    SELECT current_game.game_date - prev_game.game_date
                    FROM game_features prev_game
                    WHERE (prev_game.home_team = current_game.home_team OR prev_game.away_team = current_game.home_team)
                    AND prev_game.game_date < current_game.game_date
                    ORDER BY prev_game.game_date DESC
                    LIMIT 1
                ),
                away_rest = (
                    -- away team's previous game
                    SELECT current_game.game_date - prev_game.game_date
                    FROM game_features prev_game
                    WHERE (prev_game.home_team = current_game.away_team OR prev_game.away_team = current_game.away_team)
                    AND prev_game.game_date < current_game.game_date
                    ORDER BY prev_game.game_date DESC
                    LIMIT 1
                )
            """)
            
            rows_updated = cur.rowcount
            
        conn.commit()
    
    log.info("")
    log.info(f"✅ Successfully updated {rows_updated} games")
    log.info(f"   Columns updated: home_rest, away_rest")
    log.info(f"   Note: Games with no previous game will have NULL values")
    log.info("=" * 80)

if __name__ == "__main__":
    main()
# pipelines/etl/update_game_features_injuries.py
"""
Update game_features table with injuries, recent (within 7 days) & total

Uses player_injuries (which has current league injuries)
to populate the new recent and total injuries in game_features.

Run this after:
1.
2.
"""
import logging
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)



def main():
    """Update game_features with injury data from player_injuries."""
    
    log.info("=" * 80)
    log.info("UPDATING GAME FEATURES WITH INJURY DATA")
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
                    home_recent_injuries = (
                        SELECT COUNT(*)
                        FROM player_injuries pi
                        WHERE pi.team_abbr = gf.home_team
                          AND pi.is_current = TRUE
                          AND pi.date_injured BETWEEN (gf.game_date - INTERVAL '7 days') AND gf.game_date
                    ),
                    away_recent_injuries = (
                        SELECT COUNT(*)
                        FROM player_injuries pi
                        WHERE pi.team_abbr = gf.away_team
                          AND pi.is_current = TRUE
                          AND pi.date_injured BETWEEN (gf.game_date - INTERVAL '7 days') AND gf.game_date
                    ),
                    home_total_injuries = (
                        SELECT COUNT(*)
                        FROM player_injuries pi
                        WHERE pi.team_abbr = gf.home_team
                          AND pi.is_current = TRUE
                          AND pi.date_injured <= gf.game_date
                    ),
                    away_total_injuries = (SELECT COUNT(*)
                                           FROM player_injuries pi
                                           WHERE pi.team_abbr = gf.away_team
                                             AND pi.is_current = TRUE
                                             AND pi.date_injured <= gf.game_date
                    )
            """)
            
            conn.commit()
            
        log.info("Updated injury counts for all games")
        
    log.info("=" * 80)
    log.info("INJURY FEATURES UPDATE COMPLETE")
    log.info("=" * 80)
    
  
if __name__ == "__main__":
    main()
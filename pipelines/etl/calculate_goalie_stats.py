# pipelines/etl/calculate_goalie_stats.py
"""
Calculates goalie stats based on historical data.
Games played, home & away games, wins & losses
"""
import logging
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)


def main():
    """Calculate goalie stats"""
    
    log.info("=" * 80)
    log.info("GOALIE STATS CALCULATION")
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
                SELECT
                    goalie_id,
                    goalie_name,
                    season,
                    SUM(games_played) as games_played,
                    SUM(wins) as wins,
                    SUM(losses) as losses,
                    SUM(ot_losses) as ot_losses,
                    SUM(goals_against) as goals_against,
                    ROUND(SUM(goals_against)::numeric / SUM(games_played)::numeric, 2) as gaa
                FROM (
                     -- Home goalies
                    SELECT
                        gg.home_goalie_id as goalie_id,
                        gg.home_goalie_name as goalie_name,
                        SUBSTRING(gr.game_id::text, 1, 4)::int as season,
                        COUNT(*) as games_played,
                        SUM(CASE WHEN gr.home_goals > gr.away_goals THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN gr.home_goals < gr.away_goals AND gr.decided_in_ot_so = FALSE THEN 1 ELSE 0 END) as losses,
                        SUM(CASE WHEN gr.home_goals < gr.away_goals AND gr.decided_in_ot_so = TRUE THEN 1 ELSE 0 END) as ot_losses,
                        SUM(gr.away_goals) as goals_against
                    FROM game_goalies gg
                    JOIN game_results gr ON gg.game_id = gr.game_id
                    WHERE gg.home_goalie_id IS NOT NULL
                    GROUP BY gg.home_goalie_id, gg.home_goalie_name, SUBSTRING(gr.game_id::text, 1, 4)::int

                    UNION ALL
                    
                    -- Away goalies
                    SELECT
                        gg.away_goalie_id as goalie_id,
                        gg.away_goalie_name as goalie_name,
                        SUBSTRING(gr.game_id::text, 1, 4)::int as season,
                        COUNT(*) as games_played,
                        SUM(CASE WHEN gr.away_goals > gr.home_goals THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN gr.away_goals < gr.home_goals AND gr.decided_in_ot_so = FALSE THEN 1 ELSE 0 END) as losses,
                        SUM(CASE WHEN gr.away_goals < gr.home_goals AND gr.decided_in_ot_so = TRUE THEN 1 ELSE 0 END) as ot_losses,
                        SUM(gr.away_goals) as goals_against
                    FROM game_goalies gg
                    JOIN game_results gr ON gg.game_id = gr.game_id
                    WHERE gg.away_goalie_id IS NOT NULL
                    GROUP BY gg.away_goalie_id, gg.away_goalie_name, SUBSTRING(gr.game_id::text, 1, 4)::int
                ) combined
                GROUP BY goalie_id, goalie_name, season
                ORDER BY season, goalie_id
                    
            
            """)
            
            results = cur.fetchall()
            
            
            for row in results:
                goalie_id, goalie_name, season, gp, w, l, otl, ga, gaa = row
                
                # Upsert logic here
                cur.execute("""
                    INSERT INTO goalie_stats (
                        goalie_id, goalie_name, team_abbr, season,
                        games_played, games_started, saves, shots_against,
                        goals_against, save_pct, gaa, wins, losses,
                        ot_losses, shutouts, time_on_ice_seconds, updated_at
                    ) VALUES (
                        %s, %s, 'CALC', %s,
                        %s, NULL, NULL, NULL,
                        %s, NULL, %s, %s, %s,
                        %s, NULL, NULL, NOW()
                    )
                    ON CONFLICT (goalie_id, season) DO UPDATE SET
                        goalie_name = EXCLUDED.goalie_name,
                        games_played = EXCLUDED.games_played,
                        goals_against = EXCLUDED.goals_against,
                        gaa = EXCLUDED.gaa,
                        wins = EXCLUDED.wins,
                        losses = EXCLUDED.losses,
                        ot_losses = EXCLUDED.ot_losses,
                        updated_at = NOW()
                """, (goalie_id, goalie_name, season, gp, ga, gaa, w, l, otl))
                
        conn.commit()
        
    log.info("")
    log.info("=" * 80)
    log.info(f"Updated goalie stats for {len(results)} goalie-season combinations")
    log.info("=" * 80)

if __name__ == "__main__":
    main()
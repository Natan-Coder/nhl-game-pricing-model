# pipelines/pricing/compute_game_pricing_elos.py
from __future__ import annotations
import psycopg
from decimal import Decimal, getcontext
from datetime import datetime
from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_many  # <- use your helper that injects prepare_threshold=0
from pipelines.common.logging_setup import setup as setup_logging
from pipelines.pricing.utils import get_recent_form, apply_form_adjustment, get_rest_adjustment, calculate_goalie_advantage, get_injury_adjustment

setup_logging("INFO")
getcontext().prec = 28

# --- Tunables ---
HOME_ADVANTAGE = Decimal("50")  # Elo points for home ice (tweak)
SCALE = Decimal("400")          # logistic scale (like chess Elo)

SQL = {
    "games": """
        SELECT gf.game_id, gf.home_team, gf.away_team,
               gf.game_datetime_utc, gf.home_rest_days, gf.away_rest_days,
               gf.home_goalie_sv_pct, gf.away_goalie_sv_pct,
               gf.home_recent_injuries, gf.home_total_injuries,
               gf.away_recent_injuries, gf.away_total_injuries
        FROM game_features gf
        WHERE gf.game_type IN (2,3)              -- regular + playoffs
          AND gf.game_datetime_utc IS NOT NULL;
    """,
    "elos": """
        -- latest elo per team from team_ratings table
        SELECT team_abbr, elo
        FROM team_ratings
    """,
    "upsert": """
        INSERT INTO game_pricing (game_id, p_home_win, p_away_win)
        VALUES (%s, %s, %s)
        ON CONFLICT (game_id) DO UPDATE
           SET p_home_win = EXCLUDED.p_home_win,
               p_away_win = EXCLUDED.p_away_win;
    """,
}

def _logistic_p_home(elo_home: Decimal, elo_away: Decimal) -> Decimal:
    # Classic Elo logistic: 1 / (1 + 10^(-(diff)/scale))
    diff = (elo_home - elo_away) / SCALE
    # 10**x with Decimal
    ten_pow = (Decimal(10) ** (-diff))
    return Decimal(1) / (Decimal(1) + ten_pow)

def compute_probs_for_game(
    home_abbr: str,
    away_abbr: str,
    elos: dict[str, Decimal],
    game_date: datetime = None,
    home_rest_days: int = None,
    away_rest_days: int = None,
    home_goalie_sv_pct: Decimal = None,
    away_goalie_sv_pct: Decimal = None,
    home_recent_injuries: int = None,
    home_total_injuries: int = None,
    away_recent_injuries: int = None,
    away_total_injuries: int = None,
    conn = None
) -> tuple[Decimal, Decimal]:
    """
    Calculate win probabilities with form and rest adjustments.

    Now includes:
    RAW ELO ONLY - NO ADJUSTMENTS

    REMOVED all adjustments (comparison testing showed raw ELO performs better):
    - Recent form adjustment (adds noise)
    - Rest days adjustment (adds noise)
    - Goalie advantage adjustment (adds noise)
    - Injury adjustment (adds noise)

    Test set performance:
    - Raw ELO: 55.81% accuracy, 0.2470 Brier, 7.12% calibration error
    - With adjustments: 53.13% accuracy, 0.2498 Brier, 7.21% calibration error
    """
    eh = elos.get(home_abbr)
    ea = elos.get(away_abbr)
    if eh is None or ea is None:
        # If we don't have one, fall back to 50/50
        return Decimal("0.5"), Decimal("0.5")

    # NO ADJUSTMENTS - Use raw ELO only
    
    # Apply home advantage
    eh_eff = eh + HOME_ADVANTAGE
    p_home = _logistic_p_home(eh_eff, ea)

    # Clamp to [0,1] for safety and mirror for away
    if p_home < 0:
        p_home = Decimal(0)
    elif p_home > 1:
        p_home = Decimal(1)
    p_away = (Decimal(1) - p_home)
    return p_home, p_away

def main():
    with connect(DATABASE_URL,
        sslmode="require",
        prefer_query_mode=None,
        prepare_threshold=None,
        prepared_statement_cache_queries=None,
    ) as conn:
        with conn.cursor() as cur:
            # Load latest Elos
            cur.execute(SQL["elos"])
            elos = {abbr: Decimal(str(elo)) for abbr, elo in cur.fetchall()}

            # Pull target games (now includes game_date and rest_days)
            cur.execute(SQL["games"])
            games = cur.fetchall()  # (game_id, home_team, away_team, game_datetime_utc, home_rest_days, away_rest_days, home_goalie_sv_pct, away_goalie_sv_pct, home_recent_injuries, home_total_injuries,
            # away_recent_injuries, away_total_injuries)

            rows = []
            for gid, home, away, game_datetime, home_rest, away_rest, home_goalie_sv, away_goalie_sv, home_recent_inj, home_total_inj, away_recent_inj, away_total_inj in games:
                # Convert datetime to date for form queries
                game_date = game_datetime.date() if game_datetime else None

                # Compute probabilities with form and rest adjustments
                ph, pa = compute_probs_for_game(
                    home, away, elos,
                    game_date=game_date,
                    home_rest_days=home_rest,
                    away_rest_days=away_rest,
                    home_goalie_sv_pct=home_goalie_sv,
                    away_goalie_sv_pct=away_goalie_sv,
                    home_recent_injuries=home_recent_inj,
                    home_total_injuries=home_total_inj,
                    away_recent_injuries=away_recent_inj,
                    away_total_injuries=away_total_inj,
                    conn=conn  # Pass connection for form queries
                )
                rows.append((gid, ph, pa))

            written = 0
            if rows:
                written = execute_many(cur, SQL["upsert"], rows)
        conn.commit()

    print(f"game_pricing upserted/updated rows: {written}")
    print(f"")
    print(f"Using RAW ELO ONLY - NO ADJUSTMENTS")
    print(f"")
    print(f"Test set performance:")
    print(f"  Raw ELO:      55.81% accuracy, 0.2470 Brier, 7.12% calibration error")
    print(f"  With adjust:  53.13% accuracy, 0.2498 Brier, 7.21% calibration error")
    print(f"")
    print(f"All feature adjustments (form, rest, goalies, injuries) have been removed.")
        
if __name__ == "__main__":
    main()
import os
import math
import psycopg
from dotenv import load_dotenv
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pipelines.config import DATABASE_URL, BANKROLL
from pipelines.pricing.utils import (
    implied_prob_from_american,   # returns Decimal
    decimal_from_american,        # returns Decimal (decimal odds)
    kelly_fraction,               # kelly_fraction(p: Decimal, q: Decimal, b: Decimal) -> Decimal
)
import logging
from typing import Tuple
from pipelines.common.logging_setup import setup as setup_logging
getcontext().prec = 28     # good precision for money/odds math

setup_logging("INFO")
log = logging.getLogger(__name__)
# Try pipelines/.env first, then shared/config/.env
#here = Path(__file__).resolve()
#candidates = [
    #here.parents[1] / ".env",                         # pipelines/.env
    #here.parents[2] / "shared/config/.env",           # shared/config/.env
    #]
#for p in candidates:
    #if p.exists():
    #    load_dotenv(p, override=False)
        

SQL = {
    "latest_quotes": """
        SELECT q.game_id, q.book, q.market, q.outcome, q.american_odds, q.line_number,
               p.p_home_win, p.p_away_win
        FROM odds_quotes q
        JOIN game_pricing p ON p.game_id = q.game_id
        WHERE q.market = 'moneyline';
    """,
    "upsert_edge": """
        INSERT INTO edges (game_id, book, market, outcome, american_odds,
                           implied_prob, model_prob, edge, kelly_fraction, bankroll, suggested_stake)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (game_id, book, market, outcome, american_odds, computed_minute_utc)
            WHERE line_number IS NULL
        DO UPDATE SET
            implied_prob     = EXCLUDED.implied_prob,
            model_prob       = EXCLUDED.model_prob,
            edge             = EXCLUDED.edge,
            kelly_fraction   = EXCLUDED.kelly_fraction,
            bankroll         = EXCLUDED.bankroll,
            suggested_stake  = EXCLUDED.suggested_stake
        RETURNING (xmax = 0)::int AS inserted;  -- 1 if new insert, 0 if update
    """,
}

def model_prob_for(outcome: str, p_home, p_away) -> Decimal:
    # Ensure DB numerics come in as Decimal
    ph = Decimal(str(p_home))
    pa = Decimal(str(p_away))
    return ph if outcome == "home" else pa


def logit(p: float) -> float:
    """Convert probability to log-odds."""
    if p <= 0.0 or p >= 1.0:
        # Clip to avoid infinities
        p = max(0.001, min(0.999, p))
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    """Convert log-odds to probability."""
    if x > 20:
        return 1.0
    elif x < -20:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def apply_platt_scaling(prob: float, a: float, b: float) -> float:
    """Apply Platt Scaling transform to a probability."""
    return sigmoid(a * logit(prob) + b)


def load_active_platt_parameters() -> Tuple[float, float]:
    """Load active platt scaling parameters from database."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                    SELECT
                        param_a,
                        param_b
                    FROM calibration_params
                    WHERE is_active = TRUE
                """)
            rows = cur.fetchone()
            
            if rows:
                a = float(rows[0])  # Convert Decimal to float
                b = float(rows[1])
                return (a, b)
            
            else:
                return (1.0, 0.0)

def main() -> None:
    bankroll = Decimal(str(BANKROLL))
    
    inserted = 0
    updated = 0
    considered = 0
    
    # Load Platt scaling parameters
    a, b = load_active_platt_parameters()
    log.info(f"Using Platt scaling parameters: a={a:.4f}, b={b:.4f}")
    
    with psycopg.connect(DATABASE_URL,
        sslmode="require",
        prefer_query_mode=None,
        prepare_threshold=None,
        prepared_statement_cache_queries=None,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(SQL["latest_quotes"])
            rows = cur.fetchall()
            if not rows:
                print("No quotes found. Seed or ingest first.")
                return
            
            edge_rows = []
            for game_id, book, market, outcome, american_odds, line_number, p_home, p_away in rows:
                considered += 1
                
                # All Decimal math
                p_implied = implied_prob_from_american(american_odds)
                p_model_raw = model_prob_for(outcome, p_home, p_away)
                
                # Convert to float, apply calibration, convert back to Decimal
                p_model = Decimal(str(apply_platt_scaling(float(p_model_raw), a, b)))


                dec       = decimal_from_american(american_odds)
                edge      = p_model - p_implied
                odds_b    = dec - Decimal("1")
                p         = p_model
                q         = Decimal("1") - p
                kelly     = kelly_fraction(p, q, odds_b)
                stake     = (bankroll * kelly).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                
                edge_rows.append((
                    game_id, book, market, outcome, american_odds,
                    p_implied, p_model, edge, kelly, bankroll, stake
                ))
            
            # Batch insert all rows at once
            if edge_rows:
                # Use modified SQL without RETURNING clause for batch operation
                batch_sql = """
                    INSERT INTO edges (game_id, book, market, outcome, american_odds,
                                       implied_prob, model_prob, edge, kelly_fraction, bankroll, suggested_stake)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (game_id, book, market, outcome, american_odds, computed_minute_utc)
                        WHERE line_number IS NULL
                    DO UPDATE SET
                        implied_prob     = EXCLUDED.implied_prob,
                        model_prob       = EXCLUDED.model_prob,
                        edge             = EXCLUDED.edge,
                        kelly_fraction   = EXCLUDED.kelly_fraction,
                        bankroll         = EXCLUDED.bankroll,
                        suggested_stake  = EXCLUDED.suggested_stake;
                """
                cur.executemany(batch_sql, edge_rows)
                # Note: We lose exact insert/update counts, but gain massive speed
                inserted = len(edge_rows)  # Approximate
                updated = 0
    
            conn.commit()
    
    print(f"Edges: considered={considered}, inserted={inserted}, updated={updated}.")
    
if __name__ == "__main__":
    main()
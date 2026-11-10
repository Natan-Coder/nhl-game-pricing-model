# pipelines/pricing/compute_edges_lines.py
from __future__ import annotations

import psycopg
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pipelines.config import DATABASE_URL, BANKROLL
from pipelines.pricing.utils import implied_prob_from_american, decimal_from_american, kelly_fraction
from pipelines.model.poisson import naive_lambdas, prob_total_over, prob_spread_cover


getcontext().prec = 28
POINT_SCALE = 100  # matches ingest (e.g., 6.5 -> 650, -1.5 -> -150)

SQL = {
    "latest_totals": """
        SELECT q.game_id, q.book, q.market, q.outcome, q.american_odds, q.line_number,
               p.p_home_win, p.p_away_win
        FROM v_latest_quotes q
        JOIN game_pricing p ON p.game_id = q.game_id
        WHERE q.market = 'total';
    """,
    "latest_spreads": """
        SELECT q.game_id, q.book, q.market, q.outcome, q.american_odds, q.line_number,
               p.p_home_win, p.p_away_win
        FROM v_latest_quotes q
        JOIN game_pricing p ON p.game_id = q.game_id
        WHERE q.market = 'spread';
    """,
    "upsert_edge_line": """
        INSERT INTO edges (
            game_id, book, market, outcome, american_odds, line_number,
            implied_prob, model_prob, edge, kelly_fraction, bankroll, suggested_stake
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (game_id, book, market, outcome, american_odds, line_number, computed_minute_utc)
            WHERE line_number IS NOT NULL
        DO UPDATE SET
            implied_prob     = EXCLUDED.implied_prob,
            model_prob       = EXCLUDED.model_prob,
            edge             = EXCLUDED.edge,
            kelly_fraction   = EXCLUDED.kelly_fraction,
            bankroll         = EXCLUDED.bankroll,
            suggested_stake  = EXCLUDED.suggested_stake
        RETURNING (xmax = 0)::int AS inserted;
    """,
}

def _as_decimal(x) -> Decimal:
    return Decimal(str(x))

def _stake(bankroll: Decimal, kelly: Decimal) -> Decimal:
    # clamp negative Kelly to 0 and round to cents
    if kelly < Decimal("0"):
        kelly = Decimal("0")
    return (bankroll * kelly).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _prob_total_model(outcome: str, line_number: int, p_home_win, p_away_win) -> Decimal:
    # Very simple mapping via your naive lambdas
    lam_h, lam_a = naive_lambdas(float(p_home_win))
    pts = float(Decimal(line_number) / Decimal(POINT_SCALE))  # e.g., 650 -> 6.5
    side = "over" if outcome == "over" else "under"
    p = prob_total_over(lam_h, lam_a, pts, side)
    return _as_decimal(p)

def _prob_spread_model(outcome: str, line_number: int, p_home_win, p_away_win) -> Decimal:
    lam_h, lam_a = naive_lambdas(float(p_home_win))
    pts = float(Decimal(line_number) / Decimal(POINT_SCALE))    # e.g., -1.5 or +1.5 for the 'outcome' team
    if outcome == "home":
        p = prob_spread_cover(lam_h, lam_a, pts)
    else:
        # away side: flip the home/away in the model
        p = prob_spread_cover(lam_a, lam_h, pts)
    return _as_decimal(p)

def _build_rows_spreads(db_rows, bankroll: Decimal):
    """Return list[tuple] shaped for SQL['upsert_edge_line']."""
    out = []
    for (game_id, book, market, outcome, american_odds, line_number, p_home, p_away) in db_rows:
        if line_number is None:
            continue # spreads must have a line
        try:
            american_odds = int(american_odds)
        except Exception:
            continue
        p_implied = implied_prob_from_american(american_odds)
        p_model   = _prob_spread_model(outcome, line_number, p_home, p_away)
        dec_odds  = decimal_from_american(american_odds)
        edge      = p_model - p_implied
        b         = dec_odds - Decimal("1")
        p         = p_model
        q         = Decimal("1") - p
        kelly     = kelly_fraction(p, q, b)
        stake     = _stake(bankroll, kelly)
        out.append((
            game_id, book, market, outcome, american_odds, line_number,
            p_implied, p_model, edge, kelly, bankroll, stake
        ))
    return out

def _build_rows_totals(db_rows, bankroll: Decimal):
    out = []
    for (game_id, book, market, outcome, american_odds, line_number, p_home, p_away) in db_rows:
        if line_number is None:
            continue  # totals must have a line
        try:
            american_odds = int(american_odds)
        except Exception:
            continue
        p_implied = implied_prob_from_american(american_odds)
        p_model   = _prob_total_model(outcome, line_number, p_home, p_away)
        dec_odds  = decimal_from_american(american_odds)
        edge      = p_model - p_implied
        b         = dec_odds - Decimal("1")
        p         = p_model
        q         = Decimal("1") - p
        kelly     = kelly_fraction(p, q, b)
        stake     = _stake(bankroll, kelly)
        out.append((
            game_id, book, market, outcome, american_odds, line_number,
            p_implied, p_model, edge, kelly, bankroll, stake
        ))
    return out

def _upsert_rows(rows, conn):
    if not rows:
        return 0, 0
    
    # Batch insert all rows at once
    batch_sql = """
        INSERT INTO edges (
            game_id, book, market, outcome, american_odds, line_number,
            implied_prob, model_prob, edge, kelly_fraction, bankroll, suggested_stake
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (game_id, book, market, outcome, american_odds, line_number, computed_minute_utc)
            WHERE line_number IS NOT NULL
        DO UPDATE SET
            implied_prob     = EXCLUDED.implied_prob,
            model_prob       = EXCLUDED.model_prob,
            edge             = EXCLUDED.edge,
            kelly_fraction   = EXCLUDED.kelly_fraction,
            bankroll         = EXCLUDED.bankroll,
            suggested_stake  = EXCLUDED.suggested_stake;
    """
    
    with conn.cursor() as cur:
        cur.executemany(batch_sql, rows)
        
    # Approximate counts (we lose exact insert/update distinction)
    return len(rows), 0

def main():
    bankroll = _as_decimal(BANKROLL)
    considered = 0
    ins_total = 0
    upd_total = 0
    
    with psycopg.connect(
        DATABASE_URL,
        sslmode="require",
        prefer_query_mode=None,
        prepare_threshold=None,
        prepared_statement_cache_queries=None,
    ) as conn:
        with conn.cursor() as cur:
            # Fetch quotes once per market
            cur.execute(SQL["latest_spreads"])
            spreads_src = cur.fetchall()
            cur.execute(SQL["latest_totals"])
            totals_src = cur.fetchall()
            
        spreads_rows = _build_rows_spreads(spreads_src, bankroll)
        totals_rows = _build_rows_totals(totals_src, bankroll)
        
        # Tally and write
        for rows, label in [(spreads_rows, "spread"), (totals_rows, "total")]:
            considered += len(rows)
            ins, upd = _upsert_rows(rows, conn)
            ins_total += ins
            upd_total += upd
            
        conn.commit()
    
    print(f"Line edges: considered={considered}, inserted={ins_total}, updated={upd_total}.")
    
if __name__ == "__main__":
    main()
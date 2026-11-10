# pipelines/betting/select_bets.py
"""
Automated bet selection based on configured strategies.
Selects bets from current edges and logs them to bet_log table.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from itertools import combinations
import psycopg
import time
import random

from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_one
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

# Risk management
MAX_DAILY_EXPOSURE = 0.30  # 30% of bankroll max per day

def get_current_bankroll() -> Decimal:
    """Get today's current bankroll."""
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT COALESCE(ending_bankroll, starting_bankroll)
                FROM bankroll_state
                WHERE date = CURRENT_DATE
            """)
            result = cur.fetchone()
            if result and result[0]:
                return Decimal(str(result[0]))
            
            # If no entry for today, get most recent
            execute_one(cur, """
                SELECT ending_bankroll
                FROM bankroll_state
                ORDER BY date DESC
                LIMIT 1
            """)
            result = cur.fetchone()
            if result and result[0]:
                return Decimal(str(result[0]))
            
            # Default starting bankroll
            return Decimal("1000.00")


def get_todays_exposure() -> Decimal:
    """Calculate total pending stakes for today."""
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                             SELECT COALESCE(SUM(stake), 0)
                             FROM bet_log
                             WHERE DATE(bet_placed_at) = CURRENT_DATE
                               AND bet_status = 'pending'
                             """)
            result = cur.fetchone()
            return Decimal(str(result[0])) if result else Decimal("0")


def get_paper_bankroll() -> Decimal:
    """Get current paper money bankroll."""
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT COALESCE(ending_bankroll, starting_bankroll)
                FROM paper_bankroll_state
                WHERE date = CURRENT_DATE
            """)
            result = cur.fetchone()
            if result and result[0]:
                return Decimal(str(result[0]))
            
            # If no entry for today, get most recent
            execute_one(cur, """
                SELECT ending_bankroll
                FROM paper_bankroll_state
                ORDER BY date DESC
                LIMIT 1
            """)
            result = cur.fetchone()
            if result and result[0]:
                return Decimal(str(result[0]))
            
            # Default starting bankroll
            return Decimal("1000.00")

        
def get_paper_exposure() -> Decimal:
    """Calculate total pending stakes for paper bets today."""
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT COALESCE(SUM(stake), 0)
                FROM bet_log
                WHERE DATE(bet_placed_at) = CURRENT_DATE
                  AND bet_status = 'pending'
                  AND is_paper_money = TRUE  -- CRITICAL: Only count paper bets
            """)
            result = cur.fetchone()
            return Decimal(str(result[0])) if result else Decimal("0")


def should_skip_paper_bet(game_id: int, market: str, outcome: str, american_odds: int,
                          edge: Decimal, line_number: int = None) -> tuple[bool, str]:
    """
    Check if we should skip this paper bet due to duplicates or better existing bets.
    
    Args:
        game_id: Game identifier
        market: moneyline, spread, or total
        outcome: home, away, over, under
        american_odds: American odds (e.g., +172, -150)
        edge: Current edge for this bet (Decimal)
        line_number: Optional line number for spread/total bets
      
    Returns:
        (should_skip, reason) tuple:
            - (True, "duplicate"): Skip, exact duplicate exists
            - (True, "worse_edge"): Skip, pending bet has better/similar edge
            - (False, "new"): Place bet, no pending bet found
            - (False, "upgrade"): Place bet, edge improved significantly
    """
    UPGRADE_THRESHOLD = Decimal("0.02") # 2% edge improvement required
    
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            if line_number is not None:
                # For spread/total bets with line numbers
                execute_one(cur, """
                    SELECT american_odds, edge, bet_id
                    FROM bet_log
                    WHERE game_id = %s
                      AND market = %s
                      AND outcome = %s
                      AND line_number = %s
                      AND bet_status = 'pending'   -- Only check pending bets
                      AND is_paper_money = TRUE
                    ORDER BY bet_placed_at DESC
                    LIMIT 1
                """, (game_id, market, outcome, line_number))
            else:
                # For moneyline bets (no line number)
                execute_one(cur, """
                    SELECT american_odds, edge, bet_id
                    FROM bet_log
                    WHERE game_id = %s
                      AND market = %s
                      AND outcome = %s
                      AND line_number IS NULL
                      AND bet_status = 'pending'   -- Only check pending bets
                      AND is_paper_money = TRUE
                    ORDER BY bet_placed_at DESC
                    LIMIT 1
                """, (game_id, market, outcome))
            
            existing = cur.fetchone()
            
            if not existing:
                return (False, "new")  # No pending bet, place it
            
            existing_odds, existing_edge, existing_bet_id = existing
            existing_edge = Decimal(str(existing_edge))
            
            # Check if exact duplicates (same odds)
            if existing_odds == american_odds:
                return (True, "duplicate")
            
            # Check if edge improved significantly
            edge_improvement = edge - existing_edge
            if edge_improvement >= UPGRADE_THRESHOLD:
                return (False, "upgrade")  # Significantly better, allow it
            else:
                return (True, "worse_edge")  # Not better enough, skip it

        
def get_remaining_budget(bankroll: Decimal, current_exposure: Decimal) -> Decimal:
    """Calculate remaining budget for today."""
    max_exposure = bankroll * Decimal(str(MAX_DAILY_EXPOSURE))
    remaining = max_exposure - current_exposure
    return max(Decimal("0"), remaining)


def load_active_strategies() -> List[Dict]:
    """Load all active betting strategies from database."""
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT strategy_id, strategy_name, description,
                       min_edge, min_kelly, max_kelly, min_stake, max_stake,
                       markets, books, odds_filter,
                       kelly_multiplier, max_bets_per_day,
                       is_parlay_strategy, min_parlay_leg_prob,
                       min_parlay_edge, max_parlay_legs
                FROM betting_strategies
                WHERE is_active = TRUE
                ORDER BY strategy_id
            """)
            rows = cur.fetchall()
            
            strategies = []
            for row in rows:
                strategies.append({
                    "strategy_id": row[0],
                    "strategy_name": row[1],
                    "description": row[2],
                    "min_edge": Decimal(str(row[3])),
                    "min_kelly": Decimal(str(row[4])),
                    "max_kelly": Decimal(str(row[5])),
                    "min_stake": Decimal(str(row[6])) if row[6] else None,
                    "max_stake": Decimal(str(row[7])) if row[7] else None,
                    "markets": row[8],  # array or None
                    "books": row[9],    # array or None
                    "odds_filter": row[10],  # 'positive', 'negative', or None
                    "kelly_multiplier": Decimal(str(row[11])),
                    "max_bets_per_day": row[12],
                    "is_parlay_strategy": row[13],
                    "min_parlay_leg_prob": Decimal(str(row[14])) if row[14] else None,
                    "min_parlay_edge": Decimal(str(row[15])) if row[15] else None,
                    "max_parlay_legs": row[16],
                })
                
            return strategies
        
        
def get_bets_today_for_strategy(strategy_id: int) -> int:
    """Count how many bets this strategy has placed today."""
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT COUNT(*)
                FROM bet_log
                WHERE strategy_id = %s
                  AND DATE(bet_placed_at) = CURRENT_DATE
            """, (strategy_id,))
            result = cur.fetchone()
            return result[0] if result else 0
        

def should_skip_bet(game_id: int, market: str, outcome: str, american_odds: int,
                    edge: Decimal, line_number: int = None) -> tuple[bool, str]:
    """
    Check if we should skip this bet due to duplicates or better existing bets.
    
    Args:
        game_id: Game identifier
        market: moneyline, spread, or total
        outcome: home, away, over, under
        american_odds: American odds (e.g., +172, -150)
        edge: Current edge for this bet (Decimal)
        line_number: Optional line number for spread/total bets
      
    Returns:
        (should_skip, reason) tuple:
            - (True, "duplicate"): Skip, exact duplicate exists
            - (True, "worse_edge"): Skip, pending bet has better/similar edge
            - (False, "new"): Place bet, no pending bet found
            - (False, "upgrade"): Place bet, edge improved significantly
    """
    UPGRADE_THRESHOLD = Decimal("0.02") # 2% edge improvement required
    
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            if line_number is not None:
                # For spread/total bets with line numbers
                execute_one(cur, """
                    SELECT american_odds, edge, bet_id
                    FROM bet_log
                    WHERE game_id = %s
                      AND market = %s
                      AND outcome = %s
                      AND line_number = %s
                      AND bet_status = 'pending'   -- Only check pending bets
                    ORDER BY bet_placed_at DESC
                    LIMIT 1
                """, (game_id, market, outcome, line_number))
            else:
                # For moneyline bets (no line number)
                execute_one(cur, """
                    SELECT american_odds, edge, bet_id
                    FROM bet_log
                    WHERE game_id = %s
                      AND market = %s
                      AND outcome = %s
                      AND line_number IS NULL
                      AND bet_status = 'pending'   -- Only check pending bets
                    ORDER BY bet_placed_at DESC
                    LIMIT 1
                """, (game_id, market, outcome))
                
            existing = cur.fetchone()
            
            if not existing:
                return (False, "new")  # No pending bet, place it
            
            existing_odds, existing_edge, existing_bet_id = existing
            existing_edge = Decimal(str(existing_edge))
            
            # Check if exact duplicates (same odds)
            if existing_odds == american_odds:
                return (True, "duplicate")
            
            # Check if edge improved significantly
            edge_improvement = edge - existing_edge
            if edge_improvement >= UPGRADE_THRESHOLD:
                return (False, "upgrade")  # Significantly better, allow it
            else:
                return (True, "worse_edge")  # Not better enough, skip it
                


def query_edges_for_strategy(strategy: Dict) -> List[Dict]:
    """
    Query edges table for bets matching this strategy's criteria.
    Returns list of qualifying edges.
    """
    # Build WHERE clause based on strategy filters
    where_conditions = [
        f"e.edge >= {strategy['min_edge']}",
        f"e.kelly_fraction >= {strategy['min_kelly']}",
        f"e.kelly_fraction <= {strategy['max_kelly']}",
        "f.game_date >= CURRENT_DATE",
        "f.game_datetime_utc > (NOW() + INTERVAL '2 hours')",  # Games starting >2 hours from now
    ]
    
    # Market filter
    if strategy['markets']:
        markets_str = "', '".join(strategy['markets'])
        where_conditions.append(f"e.market IN ('{markets_str}')")
        
    # Books filter
    if strategy['books']:
        books_str = "', '".join(strategy['books'])
        where_conditions.append(f"e.book IN ('{books_str}')")
    
    # Odds filter (for underdog/favorite strategies)
    if strategy['odds_filter'] == 'positive':
        where_conditions.append("e.american_odds > 0")
    elif strategy['odds_filter'] == 'negative':
        where_conditions.append("e.american_odds < 0")
        
    where_clause = " AND ".join(where_conditions)
    
    sql = f"""
        SELECT DISTINCT ON (e.game_id, e.book, e.market, e.outcome, e.american_odds)
            e.game_id, e.book, e.market, e.outcome, e.line_number,
            e.american_odds, e.edge, e.kelly_fraction,
            e.model_prob, e.implied_prob, e.suggested_stake,
            f.home_team, f.away_team, f.game_datetime_utc
        FROM edges e
        JOIN game_features f ON e.game_id = f.game_id
        WHERE {where_clause}
        ORDER BY e.game_id, e.book, e.market, e.outcome, e.american_odds, e.edge DESC
    """
    
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            
            edges = []
            for row in rows:
                # Values from database are already calibrated (done in compute_edges.py)
                # No need to apply calibration again here
                edges.append({
                    "game_id": row[0],
                    "book": row[1],
                    "market": row[2],
                    "outcome": row[3],
                    "line_number": row[4],
                    "american_odds": row[5],
                    "edge": Decimal(str(row[6])),  # Already calibrated
                    "kelly_fraction": Decimal(str(row[7])),  # Already calibrated
                    "model_prob": Decimal(str(row[8])),  # Already calibrated
                    "implied_prob": Decimal(str(row[9])),
                    "suggested_stake": Decimal(str(row[10])),  # Already calibrated
                    "home_team": row[11],
                    "away_team": row[12],
                    "game_datetime_utc": row[13],
                })
            return edges
        

def american_to_decimal(american_odds: int) -> Decimal:
    """Convert American odds to decimal odds"""
    if american_odds > 0:
        return Decimal(american_odds) / Decimal("100") + Decimal("1")
    else:
        return Decimal("100") / Decimal(abs(american_odds)) + Decimal("1")

def calculate_home_win_probability(home_elo: Decimal, away_elo: Decimal) -> Decimal:
    """Calculate home team win probability from ELO ratings."""
    HOME_ADV = Decimal("50")
    SCALING_FACTOR = Decimal("400")
    
    home_elo_adj = home_elo + HOME_ADV
    elo_diff = (home_elo_adj - away_elo) / SCALING_FACTOR
    ten_pow = Decimal("10") ** elo_diff
    prob = ten_pow / (Decimal("1") + ten_pow)
    
    return prob


def log_live_prediction(cur, game_id: int) -> None:
    """
    Log prediction to live_predictions table.
    
    This records the model's ELO-based prediction before the game starts,
    enabling calibration analysis later.
    
    Args:
        cur: Database cursor
        game_id: Game identifier
    """
    # Get ELO ratings for this game
    cur.execute("""
        SELECT te_home.elo, te_away.elo
        FROM game_features gf
        JOIN team_ratings te_home ON te_home.team_abbr = gf.home_team
        JOIN team_ratings te_away ON te_away.team_abbr = gf.away_team
        WHERE gf.game_id = %s
    """, (game_id,))
    
    elo_result = cur.fetchone()
    
    if not elo_result:
        log.warning(f"No ELO ratings found for game {game_id}, skipping prediction log")
        return
    
    home_elo, away_elo = elo_result
    
    # Calculate home team win probability from ELOs
    home_win_prob = calculate_home_win_probability(home_elo, away_elo)
    
    # Insert prediction (or update if already exists)
    cur.execute("""
        INSERT INTO live_predictions (
            game_id, home_elo, away_elo, predicted_home_win_prob
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (game_id) DO UPDATE SET
            home_elo = EXCLUDED.home_elo,
            away_elo = EXCLUDED.away_elo,
            predicted_home_win_prob = EXCLUDED.predicted_home_win_prob,
            predicted_at = NOW()
    """, (game_id, home_elo, away_elo, home_win_prob))


def log_bet(strategy_id: int, edge: Dict, stake: Decimal, bankroll: Decimal,
            is_parlay: bool = False, parlay_id: Optional[int] = None) -> int:
    """
    Log a bet to the bet_log table.
    """
    decimal_odds = american_to_decimal(edge['american_odds'])
    
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # ===== NEW CODE: Log prediction BEFORE bet =====
            log_live_prediction(cur, edge['game_id'])
            # ================================================
            cur.execute("""
                INSERT INTO bet_log (
                    strategy_id, game_id, book, market, outcome, line_number,
                    american_odds, decimal_odds, stake,
                    model_prob, implied_prob, edge, kelly_fraction,
                    bet_status, is_parlay, parlay_id, game_start_time
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING bet_id
            """, (
                strategy_id,
                edge['game_id'],
                edge['book'],
                edge['market'],
                edge['outcome'],
                edge['line_number'],
                edge['american_odds'],
                decimal_odds,
                stake,
                edge['model_prob'],
                edge['implied_prob'],
                edge['edge'],
                edge['kelly_fraction'],
                'pending',
                is_parlay,
                parlay_id,
                edge['game_datetime_utc'],
            ))
            bet_id = cur.fetchone()[0]
            conn.commit()
            return bet_id
        
        
def select_single_bets(strategy: Dict, edges: List[Dict], bankroll: Decimal,
                       remaining_budget: Decimal) -> Tuple[int, Decimal]:
    """
    Select and log single bets for a non-parlay strategy.
    Returns (num_bets_selected, total_stake_used).
    """
    bets_today = get_bets_today_for_strategy(strategy['strategy_id'])
    max_bets = strategy['max_bets_per_day']
    
    if bets_today >= max_bets:
        log.info(f"  {strategy['strategy_name']}: Already hit max bets ({bets_today}/{max_bets})")
        return 0, Decimal("0")
    
    num_selected = 0
    total_stake = Decimal("0")
    remaining_slots = max_bets - bets_today
    
    for edge in edges:
        if num_selected >= remaining_slots:
            break
            
        # Check if this exact bet was already placed today
        should_skip, reason = should_skip_bet(
            edge['game_id'],
            edge['market'],
            edge['outcome'],
            edge['american_odds'],
            edge['edge'],
            edge['line_number']
        )
        
        if should_skip:
            if reason == "duplicate":
                log.debug(f"  Skipping {edge['home_team']} vs {edge['away_team']} "
                        f"{edge['market']} {edge['outcome']} {edge['american_odds']:+d} - exact duplicate")
            elif reason == "worse_edge":
                log.debug(f"  Skipping {edge['home_team']} vs {edge['away_team']} "
                          f"{edge['market']} {edge['outcome']} {edge['american_odds']:+d} - pending bet has better edge")
            continue  # Skip this edge and move to the next
        elif reason == "upgrade":
            log.info(f"  UPGRADE: {edge['home_team']} vs {edge['away_team']} "
                     f"{edge['market']} {edge['outcome']} {edge['american_odds']:+d} - edge improved by 2%+")
            
            
        # Calculate stake using strategy's Kelly multiplier
        kelly_stake = bankroll * edge['kelly_fraction'] * strategy['kelly_multiplier']
        
        # Apply min/max stake limits
        if strategy['min_stake'] and kelly_stake < strategy['min_stake']:
            kelly_stake = strategy['min_stake']
        if strategy['max_stake'] and kelly_stake > strategy['max_stake']:
            kelly_stake = strategy['max_stake']
            
        # Round to 2 decimals
        stake = kelly_stake.quantize(Decimal("0.01"))
        
        # Check if we have budget remaining
        if stake > remaining_budget:
            log.warning(f"  {strategy['strategy_name']}: Skipping bet, would exceed daily budget (need ${stake}, have ${remaining_budget:.2f})")
            break
            
        # Log the bet
        bet_id = log_bet(strategy['strategy_id'], edge, stake, bankroll)
        
        log.info(f"  [X] Bet {bet_id}: {edge['home_team']} vs {edge['away_team']} | "
                 f"{edge['book']} {edge['market']} {edge['outcome']} {edge['american_odds']:+d} | "
                 f"Edge: {edge['edge']:.1%} | Stake: ${stake:.2f}")
        
        num_selected += 1
        total_stake += stake
        remaining_budget -= stake
        
    return num_selected, total_stake


def select_parlay_bets(strategy: Dict, edges: List[Dict], bankroll: Decimal,
                       remaining_budget: Decimal) -> Tuple[int, Decimal]:
    """
    Select and log parlay bets for a parlay strategy.
    Returns (num_parlays_selected, total_stake_used).
    """
    bets_today = get_bets_today_for_strategy(strategy['strategy_id'])
    max_bets = strategy['max_bets_per_day']
    
    if bets_today >= max_bets:
        log.info(f"   {strategy['strategy_name']}: Already hit max bets ({bets_today}/{max_bets})")
        return 0, Decimal("0")
    
    remaining_slots = max_bets - bets_today
    
    # Filter edges that meet minimum parlay leg probability requirement
    if strategy['min_parlay_leg_prob']:
        eligible_edges = [
            e for e in edges
            if e['model_prob'] >= strategy['min_parlay_leg_prob']
        ]
        log.info(f"   {strategy['strategy_name']}: {len(eligible_edges)}/{len(edges)} edges meet min parlay leg prob")
    else:
        eligible_edges = edges
        
    if len(eligible_edges) < 2:
        log.info(f"   {strategy['strategy_name']}: Not enough edges for parlays (need at least 2)")
        return 0, Decimal("0")
    
    # Track parlays selected
    num_selected = 0
    total_stake = Decimal("0")
    
    # Generate parlay combinations (2 to max_parlay_legs)
    max_legs = strategy['max_parlay_legs'] or 3  # Default to 3 if not set
    
    # We'll try from smallest to largest parlay size
    for num_legs in range(2, min(max_legs + 1, len(eligible_edges) + 1)):
        if num_selected >= remaining_slots:
            break  # Hit our daily limit
            
        # Generate all combinations of this size
        parlay_combos = list(combinations(eligible_edges, num_legs))
    
        # Evaluate each combination
        evaluated_parlays = []
        for combo in parlay_combos:
            # Calculate combined parlay odds (multiply decimal odds)
            parlay_decimal_odds = Decimal("1")
            model_prob_combined = Decimal("1")
        
            for edge in combo:
                edge_decimal_odds = american_to_decimal(edge['american_odds'])
                parlay_decimal_odds *= edge_decimal_odds
                model_prob_combined *= edge['model_prob']
            
            # Calculate parlay edge
            parlay_implied_prob = Decimal("1") / parlay_decimal_odds
            parlay_edge = model_prob_combined - parlay_implied_prob
        
            # Filter by minimum edge
            if parlay_edge >= strategy['min_parlay_edge']:
                evaluated_parlays.append({
                    'combo': combo,
                    'parlay_decimal_odds': parlay_decimal_odds,
                    'model_prob': model_prob_combined,
                    'implied_prob': parlay_implied_prob,
                    'edge': parlay_edge,
                })
            
        # Sort by edge (best first)
        evaluated_parlays.sort(key=lambda p: p['edge'], reverse=True)
    
        # Select parlays from this leg count
        for parlay in evaluated_parlays:
            if num_selected >= remaining_slots:
                break  # Hit daily limit
            
            # Calculate Kelly stake for the parlay
            # Kelly fraction = (model_prob * parlay_odds - 1) / (parlay_odds - 1)
            kelly_fraction = (
                (parlay['model_prob'] * parlay['parlay_decimal_odds'] - Decimal("1"))
                / (parlay['parlay_decimal_odds'] - Decimal("1"))
            )
        
            # Apply Kelly multiplier and bankroll
            kelly_stake = bankroll * kelly_fraction * strategy['kelly_multiplier']
        
            # Apply min/max stake limits
            if strategy['min_stake'] and kelly_stake < strategy['min_stake']:
                kelly_stake = strategy['min_stake']
            if strategy['max_stake'] and kelly_stake > strategy['max_stake']:
                kelly_stake = strategy['max_stake']
            
            # Round to 2 decimals
            stake = kelly_stake.quantize(Decimal("0.01"))
        
            # Check budget
            if stake > remaining_budget:
                log.warning(f"   {strategy['strategy_name']}: Skipping parlay, would exceed daily budget")
                continue  # Try next parlay
            
            # Generate a unique parlay ID (using timestamp + random component)
            parlay_id = int(time.time() * 1000) + random.randint(0, 999)
        
            # Log each leg of the parlay
            leg_descriptions = []
            for edge in parlay['combo']:
                log_bet(strategy['strategy_id'], edge, stake, bankroll,
                        is_parlay=True, parlay_id=parlay_id)
                leg_descriptions.append(
                    f"{edge['outcome']} {edge['american_odds']:+d}"
                )
            
            # Log summary
            parlay_odds_american = int((parlay['parlay_decimal_odds'] - 1) * 100) if parlay['parlay_decimal_odds'] >= 2 else int(-100 / (parlay['parlay_decimal_odds'] - 1))
            log.info(f"  [X] Parlay {parlay_id}: {num_legs}-leg | " +
                    " & ".join(leg_descriptions) +
                    f" | Combined odds: {parlay_odds_american:+d} | "
                    f"Edge: {parlay['edge']:.1%} | Stake: ${stake:.2f}")
        
            num_selected += 1
            total_stake += stake
            remaining_budget -= stake
        
    return num_selected, total_stake


def main():
    """Main execution: select bets for all active strategies"""
    log.info("=" * 60)
    log.info("Starting bet selection process")
    log.info("=" * 60)
    
    # Get current bankroll and exposure
    bankroll = get_current_bankroll()
    current_exposure = get_todays_exposure()
    remaining_budget = get_remaining_budget(bankroll, current_exposure)
    
    log.info(f"Bankroll: ${bankroll:.2f}")
    log.info(f"Today's exposure: ${current_exposure:.2f} ({current_exposure/bankroll:.1%} of bankroll)")
    log.info(f"Remaining budget: ${remaining_budget:.2f} (max {MAX_DAILY_EXPOSURE:.0%} daily)")
    log.info("")
    
    # Load active strategies
    strategies = load_active_strategies()
    log.info(f"Found {len(strategies)} active strategies")
    log.info("")
    
    # Track overall stats
    total_bets_placed = 0
    total_stake_used = Decimal("0")
    
    # Process each strategy
    for strategy in strategies:
        log.info(f"Processing: {strategy['strategy_name']}")
        log.info(f"    Description: {strategy['description']}")
        
        # Query edges for this strategy
        edges = query_edges_for_strategy(strategy)
        log.info(f"    Found {len(edges)} qualifying edges")
        
        if len(edges) == 0:
            log.info(f"    No edges found, skipping")
            log.info("")
            continue
            
        # Route to appropriate function based on strategy type
        if strategy['is_parlay_strategy']:
            num_bets, stake = select_parlay_bets(strategy, edges, bankroll, remaining_budget)
        else:
            num_bets, stake = select_single_bets(strategy, edges, bankroll, remaining_budget)
            
        # Update tracking
        total_bets_placed += num_bets
        total_stake_used += stake
        remaining_budget -= stake
        
        log.info(f"   Selected {num_bets} bets, total stake: ${stake:.2f}")
        log.info("")
        
    # Final summary
    log.info("=" * 60)
    log.info("Bet selection complete")
    log.info(f"Total bets placed: {total_bets_placed}")
    log.info(f"Total stake: ${total_stake_used:.2f}")
    log.info(f"Remaining budget: ${remaining_budget:.2f}")
    log.info("=" * 60)
    
if __name__ == "__main__":
    main()
    
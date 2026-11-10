# pipelines/betting/record_results.py
"""
Record results for completed games and update bet statuses.
Updates profit/loss and bankroll state.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_one, execute_many
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

def find_completed_games_with_pending_bets() -> List[int]:
    """
    Find game_ids that have finished and have pending bets
    Only returns games that have results recorded.
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT b.game_id, gf.game_datetime_utc
                FROM bet_log b
                JOIN game_features gf ON b.game_id = gf.game_id
                WHERE b.bet_status = 'pending'
                  AND gf.game_datetime_utc < NOW()
                ORDER BY gf.game_datetime_utc DESC
            """)
            rows = cur.fetchall()
            
            game_ids = [row[0] for row in rows]
            log.info(f"Found {len(game_ids)} completed games with pending bets.")
            return game_ids
        
        
def get_game_result(game_id: int) -> Optional[Dict]:
    """
    Get the final result for a completed game
    Returns dict with home_goals, away_goals, decided_in_ot_so, or None if not found
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT home_goals, away_goals, decided_in_ot_so, home_team, away_team
                FROM game_results
                WHERE game_id = %s
            """, (game_id,))
            row = cur.fetchone()
            
            if not row:
                log.warning(f"No game result for game_id {game_id}")
                return None
            
            return {
                "home_goals": row[0],
                "away_goals": row[1],
                "decided_in_ot_so": row[2],
                "home_team": row[3],
                "away_team": row[4],
            }
        
        
def determine_bet_outcome(bet: Dict, game_result: Dict) -> str:
    """
    Determine if a bet won, lost, or pushed based on game result
    Returns: 'won, lost, or pushed'
    """
    market = bet["market"]
    outcome = bet["outcome"]
    home_goals = game_result["home_goals"]
    away_goals = game_result["away_goals"]
    
    # Moneyline bets
    if market == 'moneyline':
        home_won = home_goals > away_goals
        
        if outcome == 'home':
            return 'won' if home_won else 'lost'
        elif outcome == 'away':
            return 'won' if not home_won else 'lost'
        else:
            log.error(f"Unknown moneyline outcome: {outcome}")
            return 'lost'
    
    # Puckline/Spread bets (e.g., -1.5, +1.5)
    elif market in ('puckline', 'spread'):
        line = bet.get('line_number', 0)
        if line is None:
            line = 0
            
        # Calculate margin (positive = home won by that many)
        margin = home_goals - away_goals
        
        # Determine which team we bet on and their effective margin
        if 'home' in outcome.lower():
            # Betting on home team with the spread
            effective_margin = margin + (float(line) / 100)  # e.g., home -1.5 means they need to win by 2+
            return 'won' if effective_margin > 0 else 'push' if effective_margin == 0 else 'lost'
        elif 'away' in outcome.lower():
            # Betting on away team with the spread
            effective_margin = -margin + (float(line) / 100) # e.g., away +1.5 means they can lose by 1
            return 'won' if effective_margin > 0 else 'push' if effective_margin == 0 else 'lost'
        else:
            log.error(f"Unknown spread outcome: {outcome}")
            return 'lost'
        
    # Total bets (over/under)
    elif market == 'total':
        line = bet.get('line_number', 0)
        if line is None:
            log.error(f"Total bet missing line_number")
            return 'lost'
        
        total_goals = home_goals + away_goals
        line_decimal = float(line) / 100  # Convert 650 -> 6.5
        
        if outcome.lower() == 'over':
            return 'won' if total_goals > line_decimal else 'push' if total_goals == line_decimal else 'lost'
        elif outcome.lower() == 'under':
            return 'won' if total_goals < line_decimal else 'push' if total_goals == line_decimal else 'lost'
        else:
            log.error(f"Unknown total outcome: {outcome}")
            return 'lost'
        
    else:
        log.error(f"Unknown market type: {market}")
        return 'lost'
    
    
def calculated_profit_loss(bet_status: str, stake: Decimal, decimal_odds: Decimal) -> Decimal:
    """
    Calculate profit/loss for a settled bet.
    
    Args:
        bet_status: 'won', 'lost', or 'push'
        stake: Amount wagered
        decimal_odds: Decimal odds (e.g., 2.55 for +155 American)
     
    Returns:
        Profit (positive) or loss (negative) as Decimal
    """
    if bet_status == 'won':
        # Profit = stake * (decimal_odds - 1)
        profit = stake * (decimal_odds - Decimal("1"))
        return profit.quantize(Decimal("0.01"))  # Round to 2 decimal places
    
    elif bet_status == 'lost':
        # Lost the entire stake
        return -stake
    
    elif bet_status == 'push':
        # Push = refund, no profit or loss
        return Decimal("0")
    
    else:
        log.error(f"Unknown bet_status: {bet_status}")
        return Decimal("0")
    
    
def update_bet_result(bet_id: int, bet_status: str, profit_loss: Decimal) -> None:
    """
    Update a bet's status and profit/loss in the database.
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE bet_log
                SET bet_status = %s,
                    profit_loss = %s,
                    result_recorded_at = NOW()
                WHERE bet_id = %s
            """, (bet_status, profit_loss, bet_id))
            conn.commit()
            
    log.debug(f"Updated bet {bet_id}: {bet_status}, P&L: ${profit_loss:.2f}")
    
    
def process_parlay_results(parlay_id: int, game_results: Dict[int, Dict]) -> None:
    """
    Process all legs of a parlay and determine final outcome.
    All legs must win for parlay to win.
    
    Args:
        parlay_id: The parlay identifier
        game_results: Dict mapping game_id -> game result
    """
    # Get all bets for this parlay
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT bet_id, game_id, market, outcome, line_number,
                       stake, decimal_odds
                FROM bet_log
                WHERE parlay_id = %s AND is_parlay = TRUE
                ORDER BY bet_id
            """, (parlay_id,))
            rows = cur.fetchall()
            
    if not rows:
        log.warning(f"No bets found for parlay {parlay_id}")
        return
    
    # Process each leg
    leg_outcomes = []
    total_stake = Decimal("0")
    combined_odds = Decimal("1")
    
    for row in rows:
        bet_id, game_id, market, outcome, line_number, stake, decimal_odds = row
        total_stake = stake  # All legs have same stake
        combined_odds *= Decimal(str(decimal_odds))
        
        # Get game results
        game_result = game_results.get(game_id)
        if not game_result:
            log.warning(f"No result for game {game_id} in parlay {parlay_id}")
            leg_outcomes.append('lost')  # Treat missing result as loss
            continue
            
        # Build bet dict for determine_bet_outcome
        bet = {
            'market': market,
            'outcome': outcome,
            'line_number': line_number,
        }
        
        leg_status = determine_bet_outcome(bet, game_result)
        leg_outcomes.append(leg_status)
        
    # Determine parlay outcome: all must win
    if all(outcome == 'won' for outcome in leg_outcomes):
        parlay_status = 'won'
        parlay_profit = calculated_profit_loss('won', total_stake, combined_odds)
    elif any(outcome == 'push' for outcome in leg_outcomes) and not any(outcome == 'lost' for outcome in leg_outcomes):
        # All legs either won or pushed, no losses
        parlay_status = 'push'
        parlay_profit = Decimal("0")
    else:
        # Any loss = entire parlay loses
        parlay_status = 'lost'
        parlay_profit = -total_stake
        
    # Update all parlay legs with same result
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for row in rows:
                bet_id = row[0]
                cur.execute("""
                    UPDATE bet_log
                    SET bet_status = %s,
                        profit_loss = %s,
                        result_recorded_at = NOW()
                    WHERE bet_id = %s
                """, (parlay_status, parlay_profit, bet_id))
                conn.commit()
                
    log.info(f"Parlay {parlay_status} | {len(rows)} legs | P&L: ${parlay_profit:.2f}")
    
    
def update_bankroll_for_date(game_date: str) -> None:
    """
    Update bankroll_state for a specific date based on settled bets.
    
    Args:
        game_date: Date string (YYYY-MM-DD format)
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Get all settled bets for this date
            execute_one(cur, """
                SELECT
                    COUNT(*) as num_bets,
                    COALESCE(SUM(stake), 0) as total_staked,
                    COALESCE(SUM(profit_loss), 0) as total_profit_loss
                FROM bet_log
                WHERE DATE(game_start_time) = %s
                  AND bet_status IN ('won', 'lost', 'push')
            """, (game_date,))
            
            row = cur.fetchone()
            num_bets = row[0]
            total_staked = Decimal(str(row[1]))
            total_profit_loss = Decimal(str(row[2]))
            
            if num_bets == 0:
                log.warning(f"No bets found for {game_date}, skipping bankroll update")
                return
            
            # Get starting bankroll for this date
            execute_one(cur, """
                SELECT starting_bankroll, ending_bankroll
                FROM bankroll_state
                WHERE date = %s
            """, (game_date,))
            
            bankroll_row = cur.fetchone()
            if bankroll_row:
                starting_bankroll = Decimal(str(bankroll_row[0]))
            else:
                # If no entry exists, get previous dat's ending bankroll
                execute_one(cur, """
                    SELECT ending_bankroll
                    FROM bankroll_state
                    WHERE date < %s
                    ORDER BY date DESC
                    LIMIT 1
                 """, (game_date,))
                prev_row = cur.fetchone()
                starting_bankroll = Decimal(str(prev_row[0])) if prev_row else Decimal("1000.00")
                
            # Calculate new ending bankroll
            ending_bankroll = starting_bankroll + total_profit_loss
            
            # Upsert bankroll_state
            cur.execute("""
                INSERT INTO bankroll_state (date, starting_bankroll, ending_bankroll, total_staked, total_profit_loss, num_bets)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (date) DO UPDATE
                SET ending_bankroll = EXCLUDED.ending_bankroll,
                    total_staked = EXCLUDED.total_staked,
                    total_profit_loss = EXCLUDED.total_profit_loss,
                    num_bets = EXCLUDED.num_bets,
                    updated_at = NOW()
            """, (game_date, starting_bankroll, ending_bankroll, total_staked, total_profit_loss, num_bets))
            
            conn.commit()
            
            log.info(f"Bankroll updated for {game_date}: ${starting_bankroll:.2f} -> ${ending_bankroll:.2f} (${total_profit_loss:.2f})")
            
            
def refresh_materialized_views() -> None:
    """
    Refresh all materialized views used in reporting.
    
    This ensures reports show up-to-date data after recording results.
    """
    views_to_refresh = [
        "strategy_performance",
        # Add other materialized views here as needed
    ]
    
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for view_name in views_to_refresh:
                try:
                    # Refresh strategy performance view
                    cur.execute(f"REFRESH MATERIALIZED VIEW {view_name}")
                    conn.commit()
                    log.info(f"Refreshed {view_name} view")
                except Exception as e:
                    log.info(f"Failed to refresh {view_name}: {e}")
            
            
def main():
    """Main execution: record results for all completed games with pending bets"""
    log.info("=" * 60)
    log.info("Starting bet result recording")
    log.info("=" * 60)
    
    # Step 1: Find completed games
    game_ids = find_completed_games_with_pending_bets()
    
    if not game_ids:
        log.info("No completed games with pending bets to process")
        return
    
    # Step 2: Get game results for all completed games
    log.info(f"Fetching results for {len(game_ids)} games...")
    game_results = {}
    for game_id in game_ids:
        result = get_game_result(game_id)
        if result:
            game_results[game_id] = result
            
    log.info(f"Retrieved {len(game_results)} game results")
    
    if not game_results:
        log.warning("No game results found, cannot process bets")
        return
    
    # Step 3: Get all pending bets for these games
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Get single bets (non-parlay)
            game_ids_tuple = tuple(game_results.keys())
            cur.execute("""
                SELECT bet_id, game_id, market, outcome, line_number, stake, decimal_odds
                FROM bet_log
                WHERE game_id = ANY(%s)
                  AND bet_status = 'pending'
                  AND is_parlay = false
                ORDER BY bet_id
            """, (list(game_ids_tuple),))
            single_bets = cur.fetchall()
            
            # Get unique parlay IDs
            cur.execute("""
                SELECT DISTINCT parlay_id
                FROM bet_log
                WHERE game_id = ANY(%s)
                  AND bet_status = 'pending'
                  AND is_parlay = true
                  AND parlay_id IS NOT NULL
            """, (list(game_ids_tuple),))
            parlay_ids = [row[0] for row in cur.fetchall()]
            
    # Step 4: Process single bets
    log.info(f"Processing {len(single_bets)} single bets...")
    single_results = {'won': 0, 'lost': 0, 'push': 0}
    total_profit_loss = Decimal("0")
    
    for bet_id, game_id, market, outcome, line_number, stake, decimal_odds in single_bets:
        game_result = game_results.get(game_id)
        if not game_result:
            continue
            
        # Build bet dict
        bet = {
            'market': market,
            'outcome': outcome,
            'line_number': line_number,
        }
        
        # Determine outcome and calculate P&L
        bet_status = determine_bet_outcome(bet, game_result)
        profit_loss = calculated_profit_loss(bet_status, Decimal(str(stake)), Decimal(str(decimal_odds)))
        
        # Update database
        update_bet_result(bet_id, bet_status, profit_loss)
        
        # Track stats
        single_results[bet_status] += 1
        total_profit_loss += profit_loss
        
    log.info(f"Single bets: {single_results['won']} won, {single_results['lost']} lost, {single_results['push']} push")
    
    # Step 5: Process parlays
    log.info(f"Processing {len(parlay_ids)} parlay bets...")
    for parlay_id in parlay_ids:
        process_parlay_results(parlay_id, game_results)
        
    # Step 6: Update bankroll for all affected dates
    log.info("Updating bankroll state...")
    affected_dates = set()
    for game_id, result in game_results.items():
        # Get the game date from bet_log
        with connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                execute_one(cur, """
                    SELECT DISTINCT DATE(game_start_time)
                    FROM bet_log
                    WHERE game_id = %s
                """, (game_id,))
                row = cur.fetchone()
                if row and row[0]:
                    affected_dates.add(str(row[0]))
                    
    for game_date in affected_dates:
        update_bankroll_for_date(game_date)
        
    # Step 7: Refresh materialized views to update reports
    log.info("Refreshing materialized views...")
    refresh_materialized_views()
        
    # Final summary
    log.info("=" * 60)
    log.info("Result recording complete")
    log.info(f"Processed {len(single_bets)} single bets and {len(parlay_ids)} parlays")
    log.info(f"Updated bankroll for {len(affected_dates)} dates")
    log.info("=" * 60)
    
if __name__ == "__main__":
    main()
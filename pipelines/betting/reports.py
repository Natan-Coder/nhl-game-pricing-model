# pipelines/betting/reports.py
"""
Betting strategy performance reporting.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Optional
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_one
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)


def report_strategy_performance():
    """
    REPORT 1: Strategy Performance

    Shows how each of your 8 strategies is performing.
    Uses the strategy_performance materialized view which aggregates
    all bets by strategy to calculate win rates, ROI, profit, etc.
    """
    log.info("=" * 80)
    log.info("STRATEGY PERFORMANCE REPORT")
    log.info("=" * 80)
    log.info("")

    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT
                    strategy_name,
                    is_parlay_strategy,
                    total_bets,
                    wins, losses, pushes, pending,
                    win_rate,
                    total_staked, total_profit, roi,
                    avg_edge, avg_kelly, avg_stake
                FROM strategy_performance
                ORDER BY total_profit DESC NULLS LAST
            """)
            rows = cur.fetchall()

            if not rows:
                log.info("No strategy data available yet.")
                log.info("")
                return

            # Track totals across all strategies
            overall_bets = 0
            overall_staked = Decimal("0")
            overall_profit = Decimal("0")

            for row in rows:
                (name, is_parlay, total_bets, wins, losses, pushes, pending,
                 win_rate, staked, profit, roi, avg_edge, avg_kelly, avg_stake) = row

                # Handle None values
                total_bets = total_bets or 0
                wins, losses, pushes, pending = wins or 0, losses or 0, pushes or 0, pending or 0
                staked = Decimal(str(staked)) if staked else Decimal("0")
                profit = Decimal(str(profit)) if profit else Decimal("0")

                overall_bets += total_bets
                overall_staked += staked
                overall_profit += profit

                # Display strategy
                tag = " [PARLAY]" if is_parlay else ""
                log.info(f"{name}{tag}")
                log.info("-" * 60)

                settled = wins + losses + pushes
                if settled > 0:
                    win_pct = win_rate * 100 if win_rate else 0
                    log.info(f"  Record: {wins}W - {losses}L - {pushes}P | Win Rate: {win_pct:.1f}%")

                log.info(f"  Total Bets: {total_bets} ({settled} settled, {pending} pending)")

                if staked > 0:
                    roi_pct = roi * 100 if roi else 0
                    log.info(f"  Staked: ${staked:.2f} | Profit: ${profit:+.2f} | ROI: {roi_pct:+.1f}%")
                    log.info(f"  Avg Edge: {(avg_edge or 0)*100:.1f}% | Avg Kelly: {(avg_kelly or 0)*100:.1f}% | Avg Stake: ${avg_stake or 0:.2f}")
                else:
                    log.info(f"  No bets placed yet")
                log.info("")

            # Overall summary
            log.info("=" * 80)
            log.info("OVERALL SUMMARY")
            log.info("-" * 60)
            log.info(f"Total Bets: {overall_bets}")
            log.info(f"Total Staked: ${overall_staked:.2f}")
            log.info(f"Total Profit: ${overall_profit:+.2f}")
            if overall_staked > 0:
                overall_roi = (overall_profit / overall_staked) * 100
                log.info(f"Overall ROI: {overall_roi:+.1f}%")
            log.info("=" * 80)
            log.info("")


def report_daily_selection(date: Optional[str] = None):
    """
    REPORT 2: Daily Selection Report
    
    Shows all bets selected on a specific date (defaults to today).
    Useful for seeing what the automated system chose after running select_bets.
    Args:
         date: Date string in 'YYYY-MM-DD' format, or None for today
    """
    if date is None:
        date_str = "TODAY"
        date_filter = "CURRENT_DATE"
    else:
        date_str = date
        date_filter = f"'{date}'"
        
    log.info("=" * 80)
    log.info(f"DAILY SELECTION REPORT - {date_str}")
    log.info("=" * 80)
    log.info("")
    
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Get all bets placed on this date
            cur.execute(f"""
                SELECT
                    b.bet_id,
                    bs.strategy_name,
                    gf.home_team, gf.away_team,
                    gf.game_datetime_utc,
                    b.book, b.market, b.outcome, b.line_number,
                    b.american_odds, b.stake, b.edge,
                    b.is_parlay, b.parlay_id
                FROM bet_log b
                JOIN betting_strategies bs ON b.strategy_id = bs.strategy_id
                JOIN game_features gf ON b.game_id = gf.game_id
                WHERE DATE(b.bet_placed_at) = {date_filter}
                ORDER BY bs.strategy_name, gf.game_datetime_utc
            """)
            rows = cur.fetchall()
            
            if not rows:
                log.info(f"No bets selected for {date_str}")
                log.info("")
                return
            
            # Group bets by strategy
            current_strategy = None
            strategy_count = 0
            strategy_stake = Decimal("0")
            total_bets = 0
            total_stake = Decimal("0")
            
            for row in rows:
                (bet_id, strategy, home, away, game_time,
                 book, market, outcome, line_num, odds, stake, edge,
                 is_parlay, parlay_id) = row
                
                # New strategy section
                if strategy != current_strategy:
                    if current_strategy is not None:
                        log.info(f"    Subtotal: {strategy_count} bets, ${strategy_stake:.2f}")
                        log.info("")
                        
                    current_strategy = strategy
                    strategy_count = 0
                    strategy_stake = Decimal("0")
                    log.info(f"{strategy}:")
                    log.info("-" * 60)
                    
                # Format bet details
                matchup = f"{home} vs {away}"
                time_str = game_time.strftime("%b %d %H:%M") if game_time else "TBD"
                line_str = f" {line_num}" if line_num else ""
                parlay_str = f"  [Parlay #{parlay_id}]" if parlay_id else ""
                
                log.info(f"  Bet #{bet_id} | {matchup:30s} | {time_str}")
                log.info(f"           {book:12s} {market:10s} {outcome}{line_str} {odds:+5d}")
                log.info(f"           Stake: ${stake:.2f} | Edge: {edge:.1%}{parlay_str}")
                log.info("")
                
                strategy_count += 1
                strategy_stake += stake
                total_bets += 1
                total_stake += stake
                
            # Last strategy subtotal
            if current_strategy is not None:
                log.info(f"    Subtotal: {strategy_count} bets, ${strategy_stake:.2f}")
                log.info("")
                
            # Overall summary
            log.info("=" * 80)
            log.info(f"Total: {total_bets} bets, ${total_stake:.2f} stake")
            log.info("=" * 80)
            log.info("")


def report_bankroll_growth(days: int = 30):
    """
    REPORT 3: Bankroll Growth
    
    Shows day-by-day bankroll performance over time.
    Queries bankroll_state table to track starting/ending bankroll,
    daily P&L, and running balance.
    """
    log.info("=" * 80)
    log.info(f"BANKROLL GROWTH REPORT (Last {days} days)")
    log.info("=" * 80)
    log.info("")

    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, """
                SELECT date, starting_bankroll, ending_bankroll,
                       total_staked, total_profit_loss, num_bets
                FROM bankroll_state
                WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date DESC
            """, (days,))
            rows = cur.fetchall()

            if not rows:
                log.info("No bankroll history available yet.")
                log.info("")
                return

            # Header
            log.info(f"{'Date':12s} | {'Start':>10s} | {'End':>10s} | {'Bets':>5s} | {'Staked':>10s} | {'P&L':>10s} | {'ROI':>7s}")
            log.info("-" * 80)

            # Each day
            for row in rows:
                date, start_br, end_br, staked, pnl, num_bets = row
                start_br = Decimal(str(start_br))
                end_br = Decimal(str(end_br)) if end_br else start_br
                staked = Decimal(str(staked)) if staked else Decimal("0")
                pnl = Decimal(str(pnl)) if pnl else Decimal("0")
                num_bets = num_bets or 0

                daily_roi = (pnl / staked * 100) if staked > 0 else 0
                date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)

                pnl_str = f"${pnl:+.2f}"
                roi_str = f"{daily_roi:+.1f}%" if staked > 0 else "---"

                log.info(f"{date_str:12s} | ${start_br:9.2f} | ${end_br:9.2f} | {num_bets:5d} | ${staked:9.2f} | {pnl_str:>10s} | {roi_str:>7s}")

            # Overall stats
            first_row = rows[-1]
            last_row = rows[0]
            starting_bankroll = Decimal(str(first_row[1]))
            current_bankroll = Decimal(str(last_row[2])) if last_row[2] else Decimal(str(last_row[1]))
            total_pnl = current_bankroll - starting_bankroll
            overall_roi = (total_pnl / starting_bankroll * 100) if starting_bankroll > 0 else 0

            log.info("=" * 80)
            log.info(f"Starting Bankroll: ${starting_bankroll:.2f}")
            log.info(f"Current Bankroll:  ${current_bankroll:.2f}")
            log.info(f"Total P&L:         ${total_pnl:+.2f}")
            log.info(f"Overall ROI:       {overall_roi:+.1f}%")
            log.info("=" * 80)
            log.info("")


def report_platt_scaling_progress():
    """
    REPORT 4: Platt Scaling Progress
    
    Tracks progress toward collecting 200 settled moneyline bets
    needed for proper Platt scaling calibration.
    """
    log.info("=" * 80)
    log.info("PLATT SCALING DATA COLLECTION PROGRESS")
    log.info("=" * 80)
    log.info("")
    
    PLATT_SCALING_THRESHOLD = 200
    
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Get moneyline bet counts
            execute_one(cur, """
                SELECT
                    COUNT(*) FILTER (WHERE bet_status IN ('won', 'lost')) as settled_bets,
                    COUNT(*) FILTER (WHERE bet_status = 'pending') as pending_bets,
                    MIN(bet_placed_at) FILTER (WHERE bet_status IN ('won', 'lost')) as first_bet_date,
                    MAX(bet_placed_at) FILTER (WHERE bet_status IN ('won', 'lost')) as last_bet_date
                FROM bet_log
                WHERE market = 'moneyline'
            """)
            result = cur.fetchone()
            settled_bets = result[0] or 0
            pending_bets = result[1] or 0
            first_bet = result[2]
            last_bet = result[3]
            
            # Calculate progress
            progress_pct = (settled_bets / PLATT_SCALING_THRESHOLD) * 100
            bets_needed = max(0, PLATT_SCALING_THRESHOLD - settled_bets)
            
            # Estimate time to threshold
            days_elapsed = None
            bets_per_day = None
            days_remaining = None
            
            if first_bet and last_bet and settled_bets > 0:
                days_elapsed = (last_bet - first_bet).days + 1
                if days_elapsed > 0:
                    bets_per_day = settled_bets / days_elapsed
                    if bets_per_day > 0 and bets_needed > 0:
                        days_remaining = int(bets_needed / bets_per_day)
                        
            # Display progress
            log.info(f"Target: {PLATT_SCALING_THRESHOLD} settled moneyline bets for reliable Platt scaling")
            log.info("")
            log.info(f"Current Progress: {settled_bets}/{PLATT_SCALING_THRESHOLD} bets ({progress_pct:.1f}%)")
            log.info(f"Pending Bets:     {pending_bets}")
            log.info(f"Bets Needed:      {bets_needed}")
            log.info("")
            
            # Progress bar
            bar_width = 50
            filled = int(bar_width * progress_pct / 100)
            bar = "#" * filled + "-" * (bar_width - filled)
            log.info(f"[{bar}] {progress_pct:.1f}%")
            log.info("")
            
            # Time estimates
            if days_elapsed is not None:
                log.info(f"Collection Period: {days_elapsed} days")
                if bets_per_day is not None:
                    log.info(f"Average Rate:      {bets_per_day:.1f} bets/day")
                if days_remaining is not None:
                    log.info(f"Est. Days to 200:  {days_remaining} days (~{days_remaining/7:.0f} weeks)")
                log.info("")
                
            # Calibration status warning
            if settled_bets < PLATT_SCALING_THRESHOLD:
                log.info("STATUS: Using uniform -10% calibration shift")
                log.info("  - Known limitation: Inverted calibration issue")
                log.info("  - Underdogs underestimated (worse after shift)")
                log.info("  - Favorites overestimated (better after shift)")
                log.info("  - Platt scaling will fix this automatically")
            else:
                log.info("STATUS: Ready for Platt scaling!")
                log.info("  - You have enough data for reliable calibration")
                log.info("  - Run: vpy -m pipelines.analysis.train_platt_scaling")
            
            log.info("=" * 80)
            log.info("")


def main():
    """Run all betting reports."""
    log.info("")
    log.info("#" * 80)
    log.info("# BETTING SYSTEM REPORTS")
    log.info("#" * 80)
    log.info("")

    report_strategy_performance()
    report_daily_selection()
    report_bankroll_growth(days=30)
    report_platt_scaling_progress()

    log.info("Reports complete!")
    log.info("")


if __name__ == "__main__":
    main()

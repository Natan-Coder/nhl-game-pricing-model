"""
Paper Money Bet Selection

This script runs the same bet selection logic as select_bets.py,
but marks bets as 'paper' instead of 'pending' so you can track
both real and simulated performance side-by-side.

Run this daily alongside real money betting to:
1. Test more aggressive strategies without risking money
2. Collect more calibration data faster
3. Compare real vs paper performance
"""
from __future__ import annotations
import logging
import sys
from decimal import Decimal

# Import everything from select_bets
from pipelines.betting.select_bets import (
    get_paper_bankroll,
    get_paper_exposure,
    get_remaining_budget,
    load_active_strategies,
    query_edges_for_strategy,
    select_single_bets,
    select_parlay_bets,
    get_bets_today_for_strategy,
    should_skip_paper_bet,
    log_bet as real_log_bet,
    MAX_DAILY_EXPOSURE
)
from pipelines.config import DATABASE_URL
from pipelines.common.db import connect
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)


def log_paper_bet(strategy_id: int, edge: dict, stake: Decimal, bankroll: Decimal,
                  is_parlay: bool = False, parlay_id: int = None) -> int:
    """
    Log a paper money bet (same as real bet but status = 'paper').
    """
    from pipelines.betting.select_bets import american_to_decimal, log_live_prediction

    decimal_odds = american_to_decimal(edge['american_odds'])

    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Log prediction
            log_live_prediction(cur, edge['game_id'])

            # Log bet with 'paper' status
            cur.execute("""
                INSERT INTO bet_log (
                    strategy_id, game_id, book, market, outcome, line_number,
                    american_odds, decimal_odds, stake,
                    model_prob, implied_prob, edge, kelly_fraction,
                    bet_status, is_parlay, parlay_id, game_start_time, is_paper_money
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                True,
            ))
            bet_id = cur.fetchone()[0]
            conn.commit()
            return bet_id




def main(paper_bankroll: Decimal = None):
    """
    Main execution: select PAPER MONEY bets for all active strategies.

    Args:
        paper_bankroll: Optional separate bankroll for paper trading
                       (defaults to same as real bankroll)
    """
    log.info("=" * 60)
    log.info("PAPER MONEY BET SELECTION")
    log.info("=" * 60)

    # Use separate paper bankroll or match real bankroll
    if paper_bankroll is None:
        bankroll = get_paper_bankroll()
        log.info("Using same bankroll as real money")
    else:
        bankroll = paper_bankroll
        log.info(f"Using separate paper bankroll: ${paper_bankroll:.2f}")

    # Paper money has same exposure limits
    current_exposure = get_paper_exposure()  # Paper bets tracked separately
    remaining_budget = bankroll * Decimal(str(MAX_DAILY_EXPOSURE))

    log.info(f"Paper Bankroll: ${bankroll:.2f}")
    log.info(f"Daily Budget: ${remaining_budget:.2f} (max {MAX_DAILY_EXPOSURE:.0%})")
    log.info("")

    # Load strategies (can filter to only paper-enabled ones)
    strategies = load_active_strategies()
    log.info(f"Found {len(strategies)} active strategies")
    log.info("")

    # Track stats
    total_bets_placed = 0
    total_stake_used = Decimal("0")

    # Process each strategy using paper logging
    for strategy in strategies:
        log.info(f"Processing: {strategy['strategy_name']}")
        log.info(f"    Description: {strategy['description']}")

        # Query edges
        edges = query_edges_for_strategy(strategy)
        log.info(f"    Found {len(edges)} qualifying edges")

        if len(edges) == 0:
            log.info(f"    No edges found, skipping")
            log.info("")
            continue

        # Select bets (using paper logging)
        if strategy['is_parlay_strategy']:
            # Custom parlay logging for paper
            num_bets = 0
            stake = Decimal("0")
            log.info("   Skipping parlays for paper money (not implemented)")
        else:
            # Single bets - manually iterate to use paper logging
            num_bets = 0
            stake = Decimal("0")
            bets_today = 0  # Paper bets counted separately
            max_bets = strategy['max_bets_per_day']

            for edge in edges:
                if num_bets >= max_bets:
                    break

                # Check for duplicates (check against paper bets today)
                should_skip, reason = should_skip_paper_bet(
                    edge['game_id'],
                    edge['market'],
                    edge['outcome'],
                    edge['american_odds'],
                    edge['edge'],
                    edge['line_number']
                )

                if should_skip and reason == "duplicate":
                    continue

                # Calculate stake
                kelly_stake = bankroll * edge['kelly_fraction'] * strategy['kelly_multiplier']
                if strategy['min_stake'] and kelly_stake < strategy['min_stake']:
                    kelly_stake = strategy['min_stake']
                if strategy['max_stake'] and kelly_stake > strategy['max_stake']:
                    kelly_stake = strategy['max_stake']

                bet_stake = kelly_stake.quantize(Decimal("0.01"))

                if bet_stake > remaining_budget:
                    log.warning(f"  Skipping bet, would exceed daily budget")
                    break

                # Log paper bet
                bet_id = log_paper_bet(strategy['strategy_id'], edge, bet_stake, bankroll)

                log.info(f"  [PAPER] Bet {bet_id}: {edge['home_team']} vs {edge['away_team']} | "
                        f"{edge['book']} {edge['market']} {edge['outcome']} {edge['american_odds']:+d} | "
                        f"Edge: {edge['edge']:.1%} | Stake: ${bet_stake:.2f}")

                num_bets += 1
                stake += bet_stake
                remaining_budget -= bet_stake

        total_bets_placed += num_bets
        total_stake_used += stake

        log.info(f"   Selected {num_bets} paper bets, total stake: ${stake:.2f}")
        log.info("")

    # Final summary
    log.info("=" * 60)
    log.info("PAPER MONEY BET SELECTION COMPLETE")
    log.info(f"Total bets placed: {total_bets_placed}")
    log.info(f"Total stake: ${total_stake_used:.2f}")
    log.info(f"Remaining budget: ${remaining_budget:.2f}")
    log.info("=" * 60)


if __name__ == "__main__":
    # Can specify custom paper bankroll
    import sys
    if len(sys.argv) > 1:
        paper_bankroll = Decimal(sys.argv[1])
        main(paper_bankroll)
    else:
        main()  # Use same as real bankroll

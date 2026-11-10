# pipelines/run_all.py
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from typing import Iterable, List

import psycopg

# -------- config --------
DEFAULT_STEPS: list[list[str]] = [
    # ETL: Data Ingestion
    ["-u", "-m", "pipelines.etl.ingest_schedule"],
    ["-u", "-m", "pipelines.etl.ingest_results"],
    ["-u", "-m", "pipelines.betting.record_results"],
    ["-u", "-m", "pipelines.etl.ingest_odds_theoddsapi"],
    ["-u", "-m", "pipelines.etl.ingest_player_injuries"],
    ["-u", "-m", "pipelines.etl.refresh_views"],
    ["-u", "-m", "pipelines.etl.update_game_features_injuries"],

    # Pricing: Model Computation
    ["-u", "-m", "pipelines.pricing.compute_team_elos"],
    ["-u", "-m", "pipelines.pricing.compute_game_pricing_elos"],
    ["-u", "-m", "pipelines.pricing.compute_edges"],
    ["-u", "-m", "pipelines.pricing.compute_edges_lines"],
    
    # Betting: Automated bet selection
    ["-u", "-m", "pipelines.betting.select_bets"],
    
]

# Alerts step (runs after main pipeline completes successfully)
ALERTS_STEP = ["-u", "-m", "pipelines.alerts.edge_alerts"]

# Map step names to indices for selective execution
STEP_NAMES = {
    "schedule": 0,
    "results": 1,
    "record_bets": 2,
    "odds": 3,
    "injuries": 4,
    "views": 5,
    "injury_features": 6,
    "elos": 7,
    "pricing": 8,
    "edges": 9,
    "lines": 10,
    "select_bets": 11,
}

# -------- logging --------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger(__name__)

# -------- helpers ----------
def run_step(step_args: list[str], step_name: str) -> bool:
    """
    Run a single pipeline step using subprocess.
    Returns True if successful, False otherwise.
    """
    cmd = [sys.executable] + step_args
    log.info("=" * 60)
    log.info("Running: %s", step_name)
    log.info("Command: %s", " ".join(cmd))
    log.info("=" * 60)
    
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,  # Let output stream to console
            text=True,
        )
        elapsed = time.time() - start
        log.info("✓ %s completed in %.2fs", step_name, elapsed)
        return True
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start
        log.error("✗ %s failed after %.2fs with exit code %d", step_name, elapsed, e.returncode)
        return False
    except Exception as e:
        elapsed = time.time() - start
        log.error("✗ %s failed after %.2fs: %s", step_name, elapsed, str(e))
        return False
    
def run_pipeline(
    steps: list[list[str]],
    step_names: list[str],
    fail_fast: bool = True,
) -> tuple[int, int]:
    """
    Run multiple pipeline steps in sequence.
    
    Args:
        steps: List of command arguments for each step
        step_names: Human-readable names for each step
        fail_fast: If True, stop on first failure
        
    Returns:
        (succeeded_count, failed_count)
    """
    succeeded = 0
    failed = 0
    
    total_start = time.time()
    
    for i, (step_args, name) in enumerate(zip(steps, step_names), 1):
        log.info("")
        log.info("STEP %d/%d: %s", i, len(steps), name)
        
        success = run_step(step_args, name)
        
        if success:
            succeeded += 1
        else:
            failed += 1
            if fail_fast:
                log.error("Stopping pipeline due to failure (fail-fast mode)")
                break
                
    total_elapsed = time.time() - total_start
    
    log.info("")
    log.info("=" * 60)
    log.info("PIPELINE SUMMARY")
    log.info("=" * 60)
    log.info("Total time: %.2fs", total_elapsed)
    log.info("Succeeded: %d", succeeded)
    log.info("Failed: %d", failed)
    log.info("=" * 60)
    
    return succeeded, failed

# -------- main ---------
def main():
    parser = argparse.ArgumentParser(
        description="Run NHL betting model pipeline end-to-end",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all steps
  python -m pipelines.run_all
  
  # Run only specific steps
  python -m pipelines.run_all --only schedule,results,elos
  
  # Skip specific steps
  python -m pipelines.run_all --skip odds
  
  # Continue on errors instead of stopping
  python -m pipelines.run_all --no-fail-fast
  
Available steps:
  schedule    - Ingest NHL schedule
  results     - Ingest game results
  record_bets - Record results for completed bets (settle winners/losers)
  odds        - Ingest odds from The Odds API
  injuries    - Ingest current player injuries from Hockey-Reference
  views       - Refresh materialized views
  injury_features - Update game_features with injury counts
  elos        - Compute team Elo ratings
  pricing     - Compute game pricing from Elos
  edges       - Compute betting edges (moneylines)
  lines       - Compute edges for lines (spreads/totals)
  select_bets - Select and log bets based on strategy criteria

Note: Alerts run automatically after successful pipeline completion.
      Use --no-alerts to disable.
        """,
    )
    
    parser.add_argument(
        "--only",
        type=str,
        help="Run only these steps (comma-separated names)",
    )
    parser.add_argument(
        "--skip",
        type=str,
        help="Skip these steps (comma-separated names)",
    )
    parser.add_argument(
        "--fail-fast",
        dest="fail_fast",
        action="store_true",
        default=True,
        help="Stop on first failure (default)",
    )
    parser.add_argument(
        "--no-fail-fast",
        dest="fail_fast",
        action="store_false",
        help="Continue running steps even if one fails",
    )
    parser.add_argument(
        "--no-alerts",
        dest="run_alerts",
        action="store_false",
        default=True,
        help="Disable alerts after pipeline completion",
    )

    args = parser.parse_args()
    
    # Determine which steps to run
    if args.only:
        only_names = [s.strip() for s in args.only.split(",")]
        indices = []
        for name in only_names:
            if name not in STEP_NAMES:
                log.error("Unknown step name: %s", name)
                sys.exit(1)
            indices.append(STEP_NAMES[name])
        indices.sort()
    else:
        indices = list(range(len(DEFAULT_STEPS)))
        
    # Filter out skipped steps
    if args.skip:
        skip_names = [s.strip() for s in args.skip.split(",")]
        skip_indices = set()
        for name in skip_names:
            if name not in STEP_NAMES:
                log.error("Unknown step name: %s", name)
                sys.exit(1)
            skip_indices.add(STEP_NAMES[name])
        indices = [i for i in indices if i not in skip_indices]
        
    if not indices:
        log.error("No steps to run")
        sys.exit(1)
    
    # Build step list
    steps_to_run = [DEFAULT_STEPS[i] for i in indices]
    names_to_run = [list(STEP_NAMES.keys())[i] for i in indices]
    
    log.info("Starting NHL betting model pipeline")
    log.info("Steps to run: %s", ", ".join(names_to_run))
    log.info("Fail-fast: %s", args.fail_fast)
    log.info("")
    
    # Run the pipeline
    succeeded, failed = run_pipeline(
        steps_to_run,
        names_to_run,
        fail_fast=args.fail_fast,
    )

    # Run alerts if pipeline succeeded and alerts are enabled
    if failed == 0 and args.run_alerts and not args.only:
        log.info("")
        log.info("=" * 60)
        log.info("Running alerts for high-value edges...")
        log.info("=" * 60)
        alert_success = run_step(ALERTS_STEP, "alerts")
        if not alert_success:
            log.warning("Alerts failed, but pipeline was successful")

    # Exit with appropriate code
    if failed > 0:
        sys.exit(1)
    else:
        log.info("Pipeline completed successfully")
        sys.exit(0)
        
if __name__ == "__main__":
    main()
    
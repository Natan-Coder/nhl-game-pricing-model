# pipelines/alerts/edge_alerts.py
"""
Desktop notifications for high-value betting edges.
Shows top 5 edges in a single grouped notification.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import psycopg

from pipelines.config import DATABASE_URL, ALERT_MIN_EDGE, ALERT_MIN_KELLY, ALERT_MIN_STAKE
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

# State file to track previously alerted edges
STATE_FILE = Path(__file__).parent.parent.parent / "logs" / "alert_state.json"

def load_alert_state() -> Dict:
    """Load previous alert state to detect odds improvements."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_alert_state(edges: List[tuple]):
    """Save current edges to detect future improvements."""
    state = {
        "timestamp": datetime.now().isoformat(),
        "edges": {}
    }
    for edge_data in edges:
        game_id, book, market, outcome, odds, edge_pct = edge_data[:6]
        key = f"{game_id}_{book}_{market}_{outcome}"
        state["edges"][key] = {
            "odds": odds,
            "edge": float(edge_pct)
        }

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def format_notification_message(edges: List[tuple]) -> str:
    """Format top edges into a readable notification message (max 256 chars for Windows)."""
    if not edges:
        return "No high-value edges found."

    lines = []
    for i, edge_data in enumerate(edges[:5], 1):
        game_id, book, market, outcome, odds, edge_pct, stake, home, away = edge_data[:9]

        # Format odds display
        odds_str = f"{odds:+d}" if odds < 0 else f"+{odds}"

        # Shorten team names if needed
        home_short = home[:3].upper()
        away_short = away[:3].upper()
        
        # Market abbreviations
        market_abbr = {"moneyline": "ML", "spread": "SPR", "total": "TOT"}.get(market, market[:3].upper())
        
        # Book abbreviation
        book_short = book[:3]
        
        # Compact format: Game | Book | Market | Odds | Edge
        lines.append(f"{i}. {home_short}@{away_short} {book_short} {market_abbr} {odds_str} +{edge_pct:.1%}")


    return "\n".join(lines)

def send_notification(title: str, message: str):
    """Send desktop notification with sound."""
    try:
        import warnings
        import sys
        from io import StringIO
        from plyer import notification
        
        # Suppress thread errors from Windows notification system
        # (notification still works, but balloon tip display may fail)
        old_stderr = sys.stderr
        sys.stderr = StringIO()
        
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="NHL Betting Model",
                timeout=30,  # Show for 30 seconds
            )
        finally:
            sys.stderr = old_stderr
            
        # Avoid emoji in log message (encoding issues)
        log.info(f"Notification sent: {len(message)} chars")
    except Exception as e:
        log.error(f"Failed to send notification: {e}")

def get_top_edges() -> List[tuple]:
    """Query database for best edge from top 5 games."""
    sql = """
        WITH ranked_edges AS (
            SELECT
                e.game_id,
                e.book,
                e.market,
                e.outcome,
                e.american_odds,
                e.edge,
                e.suggested_stake,
                f.home_team,
                f.away_team,
                f.game_date,
                e.computed_at,
                ROW_NUMBER() OVER (
                    PARTITION BY e.game_id
                    ORDER BY e.edge DESC
                ) as rn
            FROM edges e
            JOIN game_features f ON e.game_id = f.game_id
            WHERE e.edge >= %s
              AND e.kelly_fraction >= %s
              AND e.suggested_stake >= %s
              AND f.game_date >= CURRENT_DATE
        )
        SELECT
            game_id, book, market, outcome, american_odds,
            edge, suggested_stake, home_team, away_team,
            game_date, computed_at
        FROM ranked_edges
        WHERE rn = 1
        ORDER BY edge DESC
        LIMIT 5;
    """

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (ALERT_MIN_EDGE, ALERT_MIN_KELLY, ALERT_MIN_STAKE))
            return cur.fetchall()

def check_for_improvements(current_edges: List[tuple], prev_state: Dict) -> List[tuple]:
    """Filter edges that have improved since last alert."""
    improved = []
    prev_edges = prev_state.get("edges", {})

    for edge_data in current_edges:
        game_id, book, market, outcome, odds, edge_pct = edge_data[:6]
        key = f"{game_id}_{book}_{market}_{outcome}"

        if key in prev_edges:
            prev_edge = float(prev_edges[key]["edge"])
            # Alert if edge improved by more than 1%
            if float(edge_pct) - prev_edge > 0.01:
                improved.append(edge_data)
        else:
            # New edge, include it
            improved.append(edge_data)

    return improved

def main():
    """Main alert logic."""
    log.info("Checking for high-value edges...")

    # Get top edges from database
    top_edges = get_top_edges()

    if not top_edges:
        log.info("No edges meet alert thresholds.")
        return

    # Load previous state
    prev_state = load_alert_state()

    # Check for new or improved edges
    alert_edges = check_for_improvements(top_edges, prev_state)

    if not alert_edges:
        log.info(f"Found {len(top_edges)} edges, but no new/improved opportunities.")
        return

    # Send notification
    message = format_notification_message(alert_edges)
    title = f"NHL: {len(alert_edges)} Betting Edge{'s' if len(alert_edges) > 1 else ''}"

    send_notification(title, message)

    # Save current state
    save_alert_state(top_edges)

    log.info(f"Alerted on {len(alert_edges)} edge(s)")

if __name__ == "__main__":
    main()

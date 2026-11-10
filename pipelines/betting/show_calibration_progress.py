"""
Monitor progress toward Platt Scaling threshold and current calibration.
"""
from __future__ import annotations
import psycopg
from pipelines.config import DATABASE_URL

def main():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Count moneyline bets
            cur.execute("""
                SELECT COUNT(*) FROM bet_log WHERE market = 'moneyline'
            """)
            total_bets = cur.fetchone()[0]
            
            # Count bets with outcomes
            cur.execute("""
                SELECT COUNT(*)
                FROM bet_log
                WHERE market = 'moneyline' AND bet_status IN ('won', 'lost')
            """)
            completed_bets = cur.fetchone()[0]
            
            # Calculate current calibration
            cur.execute("""
                SELECT
                    AVG(model_prob) as avg_predicted,
                    AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END) as avg_actual
                FROM bet_log
                WHERE market = 'moneyline'
                  AND bet_status IN ('won', 'lost')
            """)
            row = cur.fetchone()
            avg_predicted = row[0] if row[0] else 0
            avg_actual = row[1] if row[1] else 0
            calib_error = abs(float(avg_predicted) - float(avg_actual)) * 100
            
            # Check if active calibration exists
            cur.execute("""
                SELECT param_a, param_b, trained_on_n_bets, activated_at
                FROM calibration_params
                WHERE param_name = 'platt_scaling_moneyline' AND is_active = TRUE
            """)
            active_calib = cur.fetchone()
    
    print("=" * 80)
    print("PLATT SCALING CALIBRATION PROGRESS")
    print("=" * 80)
    print()
    print(f"Moneyline Bets Collected:")
    print(f"  Total placed: {total_bets}")
    print(f"  Completed (with outcome): {completed_bets}/200 ({completed_bets/200*100:.1f}%)")
    print(f"  Remaining: {max(0, 200 - completed_bets)} bets")
    print()
    
    if completed_bets >= 200:
        print("[x] READY TO TRAIN PLATT SCALING!")
        print()
        print("Run: python -m pipelines.analysis.train_platt_scaling")
    else:
        print(f"[!] Need {200 - completed_bets} more bets to train Platt Scaling")
        print(f"   At ~5 bets/day: {(200 - completed_bets) / 5:.1f} days remaining")
    
    print()
    print("-" * 80)
    print()
    print(f"Current Calibration (uncalibrated):")
    print(f"  Avg Predicted: {avg_predicted*100:.1f}%")
    print(f"  Avg Actual: {avg_actual*100:.1f}%")
    print(f"  Calibration Error: {calib_error:.1f}%")
    print()
    
    if active_calib:
        print("[x] Active Platt Scaling:")
        print(f"   a = {active_calib[0]:.4f}")
        print(f"   b = {active_calib[1]:.4f}")
        print(f"   Trained on {active_calib[2]} bets")
        print(f"   Activated: {active_calib[3]}")
    else:
        print("[!]  No active calibration (using raw probabilities)")
    
    print()
    print("=" * 80)
    
if __name__ == "__main__":
    main()
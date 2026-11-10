# pipelines/model/poisson.py
from __future__ import annotations
from math import exp, lgamma, log, sqrt, ceil
from functools import lru_cache

def _poisson_pmf(k: int, lam: float) -> float:
    # exp(k*ln(lam) - lam - ln(k!))
    if k < 0:
        return 0.0
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return exp(k * log(lam) - lam -lgamma(k + 1))

def _range_cutoff(lam: float) -> int:
    # cover ~6 sigmas (generous tail); enforce a floor
    return max(ceil(lam + 6.0 * sqrt(max(lam, 1e-9))), 15)

@lru_cache(maxsize=1024)
def pmf_row(lam: float, kmax: int | None = None) -> list[float]:
    if kmax is None:
        kmax = _range_cutoff(lam)
    return [_poisson_pmf(k, lam) for k in range(kmax + 1)]

def prob_total_over(lam_home: float, lam_away: float, line_points: float, side: str) -> float:
    # Total goals T ~ Poisson(lam_total)
    lam_total = max(lam_home + lam_away, 1e-9)
    kmax = _range_cutoff(lam_total)
    pmf = pmf_row(lam_total, kmax)
    
    if side == "over":
        # strict > line_points
        # if 6.5 => need T >= 7 ; if 6.0 => need T >= 7 (push on 6 loses)
        thresh = int(line_points) + 1   # works for x.0 and x.5
        return sum(pmf[thresh:]) if thresh <= kmax else 0.0
    else:  # "under"
        # strict < line_points
        # if 6.5 => T <= 6 ; if 6.0 => T <= 5 (push on 6 loses)
        thresh = int(line_points)  # floor
        upper = thresh if (abs(line_points - int(line_points)) > 1e-9) else (thresh - 1) # x.0 -> 5
        if upper < 0:
            return 0.0
        upper = min(upper, kmax)
        return sum(pmf[: upper + 1])
    
def prob_spread_cover(lam_team: float, lam_opp: float, spread_points: float) -> float:
    """
    Team with handicap 'spread_points' covers if team_goals + spread_points > opp_goals.
    Let margin m = team_goals - opp_goals. Need m > -spread_points.
    For integer m, that's m >= floor(-spread_points) + 1.
    Compute by double Poisson sum (independent goals).
    """
    kmax_t = _range_cutoff(lam_team)
    kmax_o = _range_cutoff(lam_opp)
    pmf_t = pmf_row(lam_team, kmax_t)
    pmf_o = pmf_row(lam_opp, kmax_o)
    
    need = int(-spread_points) + 1  # floor(-p) + 1
    
    prob = 0.0
    for t in range(kmax_t + 1):
        pt = pmf_t[t]
        # need t - o >= need -> o <= t - need
        o_max = t - need
        if o_max < 0:
            continue
        o_max = min(o_max, kmax_o)
        # sum_{o=0..o_max} pmf_o[o]
        # naive sum; kmax ~ 15-20 typically -> fast enough
        s = 0.0
        for o in range(o_max + 1):
            s += pmf_o[o]
        prob += pt * s
    return prob

def naive_lambdas(p_home_win: float, league_total: float = 6.2) -> tuple[float, float]:
    """
    Minimal baseline: split league-average total using p_home_win tilt.
    This is intentionally simple (we'll replace with a better model).
    """
    p = min(max(p_home_win, 0.05), 0.95)
    lam_home = league_total * p
    lam_away = max(league_total - lam_home, 0.1)
    return lam_home, lam_away

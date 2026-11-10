#from __future__ import annotations
# utils.py
from decimal import Decimal, getcontext
from typing import Optional
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.db import connect


getcontext().prec = 28   # good precision for money/odds


def implied_prob_from_american(american_odds: int | str) -> Decimal:
    o = Decimal(str(american_odds))
    d100 = Decimal(100)
    if o > 0:
        return d100 / (o + d100)
    else:
        return (-o) / ((-o) + d100)

#def american_from_prob(p: float) -> int:
    if p >= 0.5:
        return int(round(- (p / (1 - p)) * 100))
    return int(round(((1 - p) / p) * 100))


def decimal_from_american(american_odds: int | str) -> Decimal:
    o = Decimal(str(american_odds))
    d100 = Decimal(100)
    if o > 0:
        return Decimal(1) + (o / d100)
    else:
        return Decimal(1) + (d100 / (-o))


def kelly_fraction(p: Decimal, q: Decimal, b: Decimal) -> Decimal:
    # b is net odds (decimal_odds - 1)
    num = (b * p) - q
    den = b
    return Decimal(0) if den == 0 else num / den


def get_recent_form(
    team_code: str,
    before_date,
    lookback_games: int = 10,
    conn = None
) -> Decimal:
    """
    Calculate team's recent form based on last N games.
    
    Args:
        team_code: Team abbreviation (e.g., 'TOR', 'BOS')
        before_date: Calculate form for games before this date
        lookback_games: Number of recent games to analyze (default 10)
        conn: Optional database connection (reuse to avoid opening/closing repeatedly)
        
    Returns:
        form_factor: -1.0 (very cold) to +1.0 (very hot)
                     0.0 = neutral (50% win rate)
                     
    Example:
        TOR won 7 of last 10 games before 2024-11-15
        Win% = 0.70
        Form factor = (0.70 - 0.50) * 2 = +0.40
    """
    should_close = False
    if conn is None:
        conn = connect(DATABASE_URL)
        should_close = True
        
    try:
        with conn.cursor() as cur:
            # Get last N games for this team before the given date
            cur.execute("""
                WITH team_games AS (
                    SELECT
                        game_date,
                        CASE
                            WHEN home_team = %s THEN
                                CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END
                            WHEN away_team = %s THEN
                                CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END
                        END as won
                    FROM game_results
                    WHERE (home_team = %s OR away_team = %s)
                      AND game_date < %s
                      AND home_goals IS NOT NULL
                      AND away_goals IS NOT NULL
                    ORDER BY game_date DESC
                    LIMIT %s
                )
                SELECT
                    COUNT(*) as games_played,
                    SUM(won) as wins
                FROM team_games
            """, (team_code, team_code, team_code, team_code, before_date, lookback_games))
            
            row = cur.fetchone()
            if not row or row[0] == 0:
                # Team hasn't played enough games yet
                return Decimal("0")
            
            games_played = row[0]
            wins = row[1] or 0
            
            # Calculate win percentage
            win_pct = Decimal(str(wins)) / Decimal(str(games_played))
            
            # Convert to form factor: -1 to +1
            # 50% win rate = neutral (0)
            # 100% win rate = +1
            # 0% win rate = -1
            form_factor = (win_pct - Decimal("0.5")) * Decimal("2")
            
            return form_factor
        
    finally:
        if should_close:
            conn.close()


def apply_form_adjustment(
        base_elo: Decimal,
        form_factor: Decimal,
        max_adjustment: Decimal = Decimal("30")
) -> Decimal:
    """
    Apply recent form adjustment to base ELO rating.
    
    Args:
        base_elo: Team's base ELO rating (e.g., 1500)
        form_factor: Recent form from -1.0 to +1.0 (from get_recent_form())
        max_adjustment: Maximum ELO boost/penalty (default 30)
    
    Returns:
        Adjusted ELO rating
    
    Example:
        Team has base ELO of 1500
        Form factor is +0.40 (won 7 of last 10)
        Max adjustment is 30
        
        Adjustment = 0.40 * 30 = +12 ELO
        Adjusted ELO = 1500 + 12 = 1512
    """
    adjustment = form_factor * max_adjustment
    return base_elo + adjustment

def get_rest_adjustment(rest_days: Optional[int]) -> Decimal:
    """
    Calculate ELO adjustment based on days of rest.
    
    Teams on back-to-back games (0 days rest) win only ~42% vs rested opponents,
    representing an ~8% disadvantage, which translates to ~40 ELO points.
    
    Args:
        rest_days: Number of days since last game (None for first game of season)
      
    Returns:
        ELO adjustment (negative for fatigue, positive for extra rest)
      
    Examples:
        >>> get_rest_adjustment(0)   # Back-to-back
        Decimal('-40')
        
        >>> get_rest_adjustment(1)   # One day rest
        Decimal('-10')
        
        >>> get_rest_adjustment(2)   # Normal rest
        Decimal('0')
        
        >>> get_rest_adjustment(4)   # Extra rest
        Decimal('5')
        
        >>> get_rest_adjustment(None)  # First game of season
        Decimal('0')
    """
    if rest_days is None:
        # First game of season - assume normal rest
        return Decimal("0")
    
    if rest_days == 0:
        # Back-to-back penalty (fatigued)
        return Decimal("-40")
    elif rest_days == 1:
        # Minimal rest penalty (still tired)
        return Decimal("-10")
    elif rest_days >= 3:
        # Extra rest bonus (fresh)
        return Decimal("5")
    else:
        # Normal rest (2 days)
        return Decimal("0")


def temperature_scale(prob: Decimal, temperature: Decimal = Decimal("1.0")) -> Decimal:
    """
    Apply temperature scaling to calibrate probabilities.
    
    Temperature scaling adjusts model confidence:
    - T > 1: Less confident (probabilities move toward 50%)
    - T < 1: More confident (probabilities move away from 50%)
    - T = 1: No change
    
    Args:
        prob: Original probability (0.0 to 1.0)
        temperature: Scaling temperature (typically 0.5 to 2.0)
    
    Returns:
        Scaled probability
    
    Examples:
        Reducing overconfidence (T=1.3):
        >>> temperature_scale(Decimal("0.60"), Decimal("1.3"))
        Decimal("0.548...")  # 60% → 54.8% (closer to 50%)
        
        >>> temperature_scale(Decimal("0.40"), Decimal("1.3"))
        Decimal("0.451...")  # 40% → 45.1% (closer to 50%)
    
    Theory:
        For overconfident models, T > 1 reduces confidence.
        For underconfident models, T < 1 increases confidence.
        
        Formula:
        1. odds = p / (1 - p)
        2. scaled_odds = odds ^ (1 / T)
        3. scaled_p = scaled_odds / (1 + scaled_odds)
    """
    # Handle edge cases
    if prob <= Decimal("0") or prob >= Decimal("1"):
        return prob  # Can't scale 0 or 1
    
    if temperature == Decimal("1.0"):
        return prob  # No scaling needed
    
    # Convert probability to odds
    odds = prob / (Decimal("1") - prob)
    
    # Apply temperature scaling
    # scaled_odds = odds ^ (1/T)
    inv_temp = Decimal("1") / temperature
    
    # Use Python's ** operator for decimal exponentiation
    # Convert to float for exponentiation, then back to Decimal
    scaled_odds = Decimal(str(float(odds) ** float(inv_temp)))
    
    # Convert back to probability
    scaled_prob = scaled_odds / (Decimal("1") + scaled_odds)
    
    return scaled_prob


def shift_calibration(prob: Decimal, shift: Decimal = Decimal("0.10")) -> Decimal:
    """
    Apply shift calibration to correct systematic bias.
    
    Shift calibration adds/subtracts a fixed amount to all probabilities
    to correct for consistent over/underconfidence.
    
    Args:
        prob: Original probability (0.0 to 1.0)
        shift: Amount to shift (positive = shift down, negative = shift up)
               Default 0.10 = subtract 10% to correct overconfidence
    
    Returns:
        Calibrated probability (clamped to 0.01-0.99 to avoid edge cases)
    
    Examples:
        Correcting overconfidence (shift=0.10):
        >>> shift_calibration(Decimal("0.569"), Decimal("0.10"))
        Decimal("0.469")  # 56.9% → 46.9%
        
        >>> shift_calibration(Decimal("0.439"), Decimal("0.10"))
        Decimal("0.339")  # 43.9% → 33.9%
    
    Use Case:
        When your model has consistent calibration error across all predictions,
        shift calibration directly corrects the bias.
        
        Example: Model predicts 48.9% on average, actual is 38.5%
        Error = -10.4%, so shift = 0.10 brings predictions to 38.9% (close to 38.5%)
    """
    # Apply shift (subtract for overconfidence)
    calibrated = prob - shift
    
    # Clamp to reasonable range (avoid 0 or 1 which break odds calculations)
    calibrated = max(Decimal("0.01"), min(Decimal("0.99"), calibrated))
    
    return calibrated


def get_season_progress(game_date, season_start_date=None, season_end_date=None) -> Decimal:
    """
    Calculate how far into the NHL season a game falls (0.0 = start, 1.0 = end).
    
    The NHL regular season typically runs:
    - Start: Early October (Oct 10)
    - End: Mid April (Apr 15)
    - Duration: ~190 days
    
    Args:
        game_date: Date of the game (datetime.date or datetime.datetime)
        season_start_date: Optional custom season start (defaults to Oct 10 of year)
        season_end_date: Optional custom season end (defaults to Apr 15 of next year)
      
    Returns:
        Season progress from 0.0 (season start) to 1.0 (season end)
        Values can exceed 1.0 for playoff games
      
    Examples:
        >>> get_season_progress(date(2024, 10, 15))  # Early season
        Decimal("0.026...")  # ~3% into season
        
        >>> get_season_progress(date(2024, 12, 31))  # Mid season
        Decimal("0.457...")  # ~46% into season
        
        >>> get_season_progress(date(2025, 4, 10))   # Late season
        Decimal("0.947...")  # ~95% into season
    """
    from datetime import date, datetime
    
    # Convert datetime to date if needed
    if isinstance(game_date, datetime):
        game_date = game_date.date()
        
    # Determine which season this game belongs to
    # If game is before July, it's the season that started last October
    # If game is after July, it's the season starting this October
    if game_date.month < 7:
        season_year = game_date.year - 1
    else:
        season_year = game_date.year
        
    # Default season dates if not provided
    if season_start_date is None:
        season_start_date = date(season_year, 10, 10)  # Oct 10
    if season_end_date is None:
        season_end_date = date(season_year + 1, 4, 15)  # Apr 15 next year
        
    # Calculate days into season
    days_into_season = (game_date - season_start_date).days
    total_season_days = (season_end_date - season_start_date).days
    
    # Calculate progress (can be negative for preseason, >1 for playoffs)
    progress = Decimal(str(days_into_season)) / Decimal(str(total_season_days))
    
    return progress


def get_season_adjustment(game_date, season_start_date=None, season_end_date=None) -> tuple[Decimal, Decimal]:
    """
    Calculate ELO adjustments based on time of season.
    
    Season effects:
    - Early season (0-10%): Teams finding chemistry, reduce home advantage
    - Mid season (10-75%): Normal play, no adjustment
    - Late season (75-100%): Playoff race intensity, reduce home advantage
    
    Args:
        game_date: Date of the game
        season_start_date: Optional custom season start
        season_end_date: Optional custom season end
      
    Returns:
        Tuple of (home_adjustment, away_adjustment) in ELO points
        
    Examples:
        Early season (Oct 15):
        >>> get_season_adjustment(date(2024, 10, 15))
        (Decimal('-10'), Decimal('0'))  # Reduce home advantage by 10 ELO
        
        Mid season (Dec 31):
        >>> get_season_adjustment(date(2024, 12, 31))
        (Decimal('0'), Decimal('0'))  # No adjustment
        
        Late season (Apr 5):
        >>> get_season_adjustment(date(2025, 4, 5))
        (Decimal('-15'), Decimal('0'))  # Reduce home advantage by 15 ELO
      
    Theory:
        Early season: Teams still gelling, home ice advantage less pronounced
        Late season: Desperate road teams play harder, home advantage reduced
    """
    progress = get_season_progress(game_date, season_start_date, season_end_date)
    
    home_adj = Decimal("0")
    away_adj = Decimal("0")
    
    if progress < Decimal("0.10"):
        # Early season (0-10%): Reduce home advantage
        home_adj = Decimal("-10")
    elif progress > Decimal("0.75"):
        # Late season (75-100%): Playoff race, reduce home advantage more
        home_adj = Decimal("-15")
    # else: Mid season, no adjustment
    
    return (home_adj, away_adj)
    
    
# ============================================================
# NHL Division Mappings (2024-25 Season)
# ============================================================

NHL_DIVISIONS = {
    # Atlantic Division
    'BOS': 'ATL',  # Boston Bruins
    'BUF': 'ATL',  # Buffalo Sabres
    'DET': 'ATL',  # Detroit Red Wings
    'FLA': 'ATL',  # Florida Panthers
    'MTL': 'ATL',  # Montreal Canadiens
    'OTT': 'ATL',  # Ottawa Senators
    'TBL': 'ATL',  # Tampa Bay Lightning
    'TOR': 'ATL',  # Toronto Maple Leafs
    
    # Metropolitan Division
    'CAR': 'MET',  # Carolina Hurricanes
    'CBJ': 'MET',  # Columbus Blue Jackets
    'NJD': 'MET',  # New Jersey Devils
    'NYI': 'MET',  # New York Islanders
    'NYR': 'MET',  # New York Rangers
    'PHI': 'MET',  # Philadelphia Flyers
    'PIT': 'MET',  # Pittsburgh Penguins
    'WSH': 'MET',  # Washington Capitals
    
    # Central Division
    'ARI': 'CEN',  # Arizona Coyotes (now Utah Hockey Club)
    'UTA': 'CEN',  # Utah Hockey Club
    'CHI': 'CEN',  # Chicago Blackhawks
    'COL': 'CEN',  # Colorado Avalanche
    'DAL': 'CEN',  # Dallas Stars
    'MIN': 'CEN',  # Minnesota Wild
    'NSH': 'CEN',  # Nashville Predators
    'STL': 'CEN',  # St. Louis Blues
    'WPG': 'CEN',  # Winnipeg Jets
    
    # Pacific Division
    'ANA': 'PAC',  # Anaheim Ducks
    'CGY': 'PAC',  # Calgary Flames
    'EDM': 'PAC',  # Edmonton Oilers
    'LAK': 'PAC',  # Los Angeles Kings
    'SJS': 'PAC',  # San Jose Sharks
    'SEA': 'PAC',  # Seattle Kraken
    'VAN': 'PAC',  # Vancouver Canucks
    'VGK': 'PAC',  # Vegas Golden Knights
    }

def is_divisional_game(home_team: str, away_team: str) -> bool:
    """
    Check if two teams are in the same division.
    
    Divisional games have different dynamics:
    - Teams play each other 4+ times per season
    - Higher familiarity and intensity
    - Rivalries are stronger
    
    Args:
        home_team: Home team code (e.g., 'TOR')
        away_team: Away team code (e.g., 'BOS')
    
    Returns:
        True if both teams are in the same division, False otherwise
    
    Examples:
        >>> is_divisional_game('TOR', 'BOS')  # Both Atlantic
        True
        
        >>> is_divisional_game('TOR', 'CHI')  # TOR=Atlantic, CHI=Central
        False
        
        >>> is_divisional_game('EDM', 'VAN')  # Both Pacific
        True
    """
    # Get divisions for both teams
    home_div = NHL_DIVISIONS.get(home_team)
    away_div = NHL_DIVISIONS.get(away_team)
    
    # If either team not found, assume not divisional
    if home_div is None or away_div is None:
        return False
    
    return home_div == away_div


def get_divisional_adjustment(home_team: str, away_team: str) -> Decimal:
    """
    Calculate ELO adjustment for divisional rivalry games.
    
    Divisional games are more competitive due to familiarity and intensity.
    This reduces home ice advantage slightly.
    
    Args:
        home_team: Home team code
        away_team: Away team code
    
    Returns:
        Home ELO adjustment (negative = reduce home advantage)
    
    Examples:
        Divisional game (TOR vs BOS):
        >>> get_divisional_adjustment('TOR', 'BOS')
        Decimal('-15')  # Reduce home advantage by 15 ELO
        
        Non-divisional game (TOR vs CHI):
        >>> get_divisional_adjustment('TOR', 'CHI')
        Decimal('0')  # No adjustment
    
    Theory:
        Divisional opponents are familiar with:
        - Each other's systems and tendencies
        - The road arena (play there 2-3x per year)
        - Key players and matchups
        
        This familiarity reduces home ice advantage from ~50 ELO to ~35 ELO.
    """
    if is_divisional_game(home_team, away_team):
        # Divisional game: Reduce home advantage
        return Decimal("-15")
    else:
        # Non-divisional game: No adjustment
        return Decimal("0")


def get_goalie_tier(save_pct: Optional[Decimal]) -> Decimal:
    """
    Return ELO adjustment based on goalie save percentage.
    
    Args:
        save_pct: Goalie's save percentage (e.g., Decimal("0.915") for 91.5%)
                  None if goalie data not available
    
    Returns:
        ELO adjustment: -40 to +40
    
    Examples:
        >>> get_goalie_tier(Decimal("0.925"))  # Elite
        40
        
        >>> get_goalie_tier(Decimal("0.915"))  # Above average
        20
        
        >>> get_goalie_tier(Decimal("0.885"))  # Poor
        -40
        
        >>> get_goalie_tier(None)  # No data
        0
    """

    if save_pct is None:
        return Decimal("0")
    
    if save_pct >= Decimal("0.920"):  # Elite
        return Decimal("40")
    elif save_pct >= Decimal("0.910"):  # Above Avg
        return Decimal("20")
    elif save_pct >= Decimal("0.900"):  # Avg
        return Decimal("0")
    elif save_pct >= Decimal("0.890"):  # Below Avg
        return Decimal("-20")
    else:   # Poor
        return Decimal("-40")
    
    
def calculate_goalie_advantage(home_sv_pct: Optional[Decimal], away_sv_pct: Optional[Decimal]) -> Decimal:
    """
    Calculate net goalie advantage for home team.
    
    Args:
        home_sv_pct: Home goalie's save percentage (or None)
        away_sv_pct: Away goalie's save percentage (or None)
    
    Returns:
        Net ELO advantage for home team (-80 to +80)
        Positive = home goalie advantage
        Negative = away goalie advantage
    
    Examples:
        Elite home goalie vs Average away goalie:
        >>> calculate_goalie_advantage(Decimal("0.925"), Decimal("0.905"))
        Decimal("40")  # +40 - 0 = +40
        
        Poor home goalie vs Elite away goalie:
        >>> calculate_goalie_advantage(Decimal("0.880"), Decimal("0.925"))
        Decimal("-80")  # -40 - 40 = -80
        
        Both average:
        >>> calculate_goalie_advantage(Decimal("0.905"), Decimal("0.905"))
        Decimal("0")  # 0 - 0 = 0
        
        No data:
        >>> calculate_goalie_advantage(None, None)
        Decimal("0")
    """
    # One line code to handle the above
    return get_goalie_tier(home_sv_pct) - get_goalie_tier(away_sv_pct)


def get_injury_adjustment(
        home_recent: Optional[int],
        home_total: Optional[int],
        away_recent: Optional[int],
        away_total: Optional[int]
        ) -> Decimal:
    """
    Calculate net injury disadvantage for teams.
    
    Recent injuries (within 7 days) are weighted more heavily as they
    cause more disruption to team chemistry and line combinations.
    
    Args:
        home_recent: Home team injuries in last 7 days
        home_total: Home team total current injuries
        away_recent: Away team injuries in last 7 days
        away_total: Away team total current injuries
    
    Returns:
        Net ELO advantage for home team
        Positive = away team more injured (home advantage)
        Negative = home team more injured (away advantage)
    
    Examples:
        Home heavily injured, away healthy:
        >>> get_injury_adjustment(2, 5, 0, 1)
        Decimal("-45")  # Home penalty 55 - Away penalty 10 = -45
        
        Both teams equally injured:
        >>> get_injury_adjustment(1, 3, 1, 3)
        Decimal("0")
        
        No injury data:
        >>> get_injury_adjustment(None, None, None, None)
        Decimal("0")
    """
    if home_recent is None or home_total is None or away_recent is None or away_total is None:
        return Decimal("0")
    
    home_penalty = (home_recent * 15) + (home_total * 5)
    away_penalty = (away_recent * 15) + (away_total * 5)
    
    return Decimal(away_penalty - home_penalty)



# def apply_platt_calibration(raw_prob: Decimal, conn=None) -> Decimal:
#     """
#     Apply Platt Scaling calibration to a raw probability.
#
#     Loads active calibration parameters from database and applies transform:
#         calibrated_prob = sigmoid(a * logit(raw_prob) + b)
#
#     Args:
#         raw_prob: Raw model probability (0.0 to 1.0)
#         conn: Optional database connection (reuse to avoid opening/closing)
#
#     Returns:
#         Calibrated probability
#
#     Examples:
#         >>> apply_platt_calibration(Decimal("0.569"))
#         Decimal("0.469")  # Corrected for overconfidence
#     """
#     import math
#     from pipelines.config import DATABASE_URL
#     from pipelines.common.db import connect
#
#     # Check if we need to load parameters
#     should_close = False
#     if conn is None:
#         conn = connect(DATABASE_URL)
#         should_close = True
#
#     try:
#         with conn.cursor() as cur:
#             # Load active calibration parameters
#             cur.execute("""
#                 SELECT param_a, param_b
#                 FROM calibration_params
#                 WHERE param_name = 'platt_scaling_moneyline'
#                     AND is_active = TRUE
#                 LIMIT 1
#             """)
#             row = cur.fetchone()
#
#             if not row:
#                 # No active calibration, return raw probability
#                 return raw_prob
#
#             a, b = row
#             a = float(a)
#             b = float(b)
#
#         # Apply Platt Scaling transform
#         # calibrated = sigmoid(a * logit(raw) + b)
#
#         # Convert to float for math operations
#         p = float(raw_prob)
#
#         # Clip to avoid log(0) or log(1)
#         p = max(0.001, min(0.999, p))
#
#         # logit(p) = log(p / (1 - p))
#         logit_p = math.log(p / (1 - p))
#
#         # Apply transform
#         transformed = a * logit_p + b
#
#         # sigmoid(x) = 1 / (1 + exp(-x))
#         if transformed > 20:
#             calibrated = 1.0
#         elif transformed < -20:
#             calibrated = 0.0
#         else:
#             calibrated = 1.0 / (1.0 + math.exp(-transformed))
#
#         # Convert back to Decimal
#         return Decimal(str(calibrated))
#
#     finally:
#         if should_close:
#             conn.close()
            
            
            

        
    
    
    
    
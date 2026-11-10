import psycopg
from pipelines.config import DATABASE_URL

conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()

print('='*100)
print('BUF vs BOS MATCHUP ANALYSIS')
print('='*100)
print()

# Get game details
cur.execute('''
    SELECT
        gf.game_id,
        gf.home_team,
        gf.away_team,
        gf.game_datetime_utc AT TIME ZONE 'America/New_York' as game_time_et,
        gp.p_home_win,
        gp.p_away_win
    FROM game_features gf
    JOIN game_pricing gp ON gf.game_id = gp.game_id
    WHERE gf.home_team = 'BUF'
      AND gf.away_team = 'BOS'
      AND gf.game_date = '2026-04-21'
''')

game_id, home, away, game_time, p_home, p_away = cur.fetchone()
print(f'Game: {home} (home) vs {away} (away)')
print(f'Time: {game_time} ET')
print(f'Model Probability: {home} {float(p_home)*100:.1f}%, {away} {float(p_away)*100:.1f}%')
print()

# Get ELO ratings
cur.execute('''
    SELECT team_abbr, elo, updated_at
    FROM team_ratings
    WHERE team_abbr IN ('BUF', 'BOS')
    ORDER BY team_abbr
''')

print('CURRENT ELO RATINGS:')
print('-'*100)
elos = {}
for team, elo, updated in cur.fetchall():
    elos[team] = float(elo)
    print(f'{team}: {float(elo):.1f} (last updated: {updated})')
print()

# Calculate raw ELO probability
buf_elo = elos['BUF']
bos_elo = elos['BOS']
elo_diff = (buf_elo + 50 - bos_elo) / 400
raw_prob = 10**elo_diff / (1 + 10**elo_diff)
print(f'Raw ELO Prediction: BUF {raw_prob*100:.1f}%, BOS {(1-raw_prob)*100:.1f}%')
print(f'ELO Advantage: BUF +{buf_elo - bos_elo:.1f} points (+50 home advantage)')
print()

# Get recent results
print('RECENT FORM (Last 5 games):')
print('-'*100)
for team in ['BUF', 'BOS']:
    cur.execute('''
        SELECT
            gr.game_date,
            CASE
                WHEN gr.home_team = %s THEN gr.away_team || ' (A)'
                ELSE gr.home_team || ' (H)'
            END as opponent,
            CASE
                WHEN gr.home_team = %s THEN gr.home_goals || '-' || gr.away_goals
                ELSE gr.away_goals || '-' || gr.home_goals
            END as score,
            CASE
                WHEN (gr.home_team = %s AND gr.home_goals > gr.away_goals) THEN 'W'
                WHEN (gr.away_team = %s AND gr.away_goals > gr.home_goals) THEN 'W'
                ELSE 'L'
            END as result
        FROM game_results gr
        WHERE (gr.home_team = %s OR gr.away_team = %s)
          AND gr.game_date < '2026-04-21'
        ORDER BY gr.game_date DESC
        LIMIT 5
    ''', (team, team, team, team, team, team))

    results = cur.fetchall()
    record = sum(1 for r in results if r[3] == 'W')
    print(f'{team}: {record}-{len(results)-record} in last {len(results)}')
    for date, opp, score, result in results:
        print(f'  {date} vs {opp:<15} {score:>5} [{result}]')
    print()

# Get logged bet details
cur.execute('''
    SELECT
        bet_id, book, market, outcome, american_odds,
        stake, model_prob, implied_prob, edge, kelly_fraction
    FROM bet_log
    WHERE bet_id = 441
''')

bet = cur.fetchone()
print('LOGGED BET DETAILS:')
print('-'*100)
print(f'Bet ID: {bet[0]}')
print(f'Book: {bet[1]}')
print(f'Market: {bet[2]} - {bet[3]}')
print(f'Odds: {bet[4]:+d}')
print(f'Stake: ${float(bet[5]):.2f}')
print(f'Model Probability: {float(bet[6])*100:.1f}%')
print(f'Implied Probability: {float(bet[7])*100:.1f}%')
print(f'Edge: {float(bet[8])*100:.1f}%')
print(f'Kelly %: {float(bet[9])*100:.2f}%')
print()

# Calculate potential returns
stake = float(bet[5])
decimal_odds = 100 / abs(bet[4]) + 1
potential_win = stake * decimal_odds - stake
print('POTENTIAL RETURNS:')
print('-'*100)
print(f'Risk: ${stake:.2f}')
print(f'To Win: ${potential_win:.2f}')
print(f'Total Return (if win): ${stake + potential_win:.2f}')
print(f'ROI (if win): {(potential_win/stake)*100:.1f}%')
print()

print('='*100)

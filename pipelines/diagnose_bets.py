#!/usr/bin/env python3
"""Diagnose bet predictions vs actual outcomes"""

from dotenv import load_dotenv
import psycopg
import os

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute('''
    SELECT
        b.game_id,
        b.outcome,
        b.model_prob,
        b.bet_status,
        b.american_odds,
        gr.home_goals,
        gr.away_goals,
        CASE WHEN gr.home_goals > gr.away_goals THEN 'home'
             WHEN gr.away_goals > gr.home_goals THEN 'away'
             ELSE 'tie' END as actual_winner
    FROM bet_log b
    JOIN game_results gr ON b.game_id = gr.game_id
    WHERE b.market = 'moneyline'
      AND b.bet_status IN ('won', 'lost')
    ORDER BY b.bet_id DESC
    LIMIT 20
''')

rows = cur.fetchall()

print('Recent Bets Analysis:')
print('=' * 100)
print(f"{'game_id':<10} | {'bet_on':<6} | {'model_prob':<11} | {'result':<6} | {'odds':<6} | {'score':<7} | {'winner':<6} | {'match?':<6}")
print('-' * 100)

matches = 0
total = 0
for row in rows:
    game_id, bet_on, model_prob, result, odds, home_goals, away_goals, winner = row
    score = f'{home_goals}-{away_goals}'

    # Check if bet_on matches actual winner
    match = '✓' if bet_on == winner else '✗'
    if bet_on == winner:
        matches += 1
    total += 1

    print(f'{game_id:<10} | {bet_on:<6} | {model_prob:.1%} ({model_prob:.3f}) | {result:<6} | {odds:>+5.0f} | {score:<7} | {winner:<6} | {match}')

print('-' * 100)
print(f'\nWin Rate: {matches}/{total} = {matches/total*100:.1f}%')
print(f'Average Model Prob: {sum(row[2] for row in rows)/len(rows)*100:.1f}%')
print()

# Check for systematic issues
print('Diagnostic Checks:')
print('-' * 100)

home_bets = [r for r in rows if r[1] == 'home']
away_bets = [r for r in rows if r[1] == 'away']

print(f'Home bets: {len(home_bets)} (won: {sum(1 for r in home_bets if r[3] == "won")})')
print(f'Away bets: {len(away_bets)} (won: {sum(1 for r in away_bets if r[3] == "won")})')
print()

# Check if high model_prob correlates with wins
high_prob_bets = [r for r in rows if r[2] > 0.5]
low_prob_bets = [r for r in rows if r[2] <= 0.5]

print(f'High prob bets (>50%): {len(high_prob_bets)} (won: {sum(1 for r in high_prob_bets if r[3] == "won")})')
print(f'Low prob bets (≤50%): {len(low_prob_bets)} (won: {sum(1 for r in low_prob_bets if r[3] == "won")})')
print()

if len(low_prob_bets) > len(high_prob_bets):
    print('⚠️  WARNING: You have more low-probability bets than high-probability bets!')
    print('   This suggests bet selection might be backwards.')

conn.close()

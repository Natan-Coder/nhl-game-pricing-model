import psycopg
from pipelines.config import DATABASE_URL

conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()

# Show pending bet
cur.execute('''
    SELECT
        bet_id,
        game_id,
        book,
        outcome,
        american_odds,
        stake,
        bet_status
    FROM bet_log
    WHERE bet_id = 441
''')

bet = cur.fetchone()
print('='*80)
print('BET #441 - READY TO PLACE')
print('='*80)
print()
print(f'Game: BUF vs BOS (April 21, 7:30 PM ET)')
print(f'Book: {bet[2]}')
print(f'Bet: Buffalo (home) @ {bet[4]:+d}')
print(f'Stake: ${float(bet[5]):.2f}')
print(f'To Win: ${float(bet[5]) * (100/abs(bet[4])):.2f}')
print(f'Status: {bet[6].upper()}')
print()
print('='*80)
print('INSTRUCTIONS:')
print('='*80)
print('1. Log into BetMGM')
print('2. Find: Buffalo Sabres vs Boston Bruins (tomorrow 7:30 PM ET)')
print('3. Bet: Buffalo Moneyline')
print('4. Verify odds are -165 or better')
print('5. Enter stake: $6.69')
print('6. Confirm and place bet')
print()
print('The bet will remain PENDING in the system until the game finishes tomorrow.')
print('After the game, run the outcome update script to mark it won/lost.')
print('='*80)

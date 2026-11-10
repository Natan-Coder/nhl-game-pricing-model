-- Latest quote per (game, book, market, outcome)
CREATE OR REPLACE VIEW latest_quotes AS
SELECT DISTINCT ON (game_id, book, market, outcome)
       id, game_id, book, market, outcome, american_odds, line_number, captured_at
FROM odds_quotes
ORDER BY game_id, book, market, outcome, captured_at DESC;

-- Helper: decimal odds for ordering
CREATE OR REPLACE VIEW latest_quotes_with_decimal AS
SELECT *,
       CASE
         WHEN american_odds > 0 THEN 1 + (american_odds / 100.0)
         ELSE 1 + (100.0 / (-american_odds))
       END AS decimal_odds
FROM latest_quotes;

-- Best (most favorable to bettor) moneyline per (game, outcome) across all books
CREATE OR REPLACE VIEW best_moneyline_quotes AS
SELECT DISTINCT ON (game_id, outcome)
       game_id, outcome, book, american_odds, decimal_odds, captured_at
FROM latest_quotes_with_decimal
WHERE market = 'moneyline'
ORDER BY game_id, outcome, decimal_odds DESC, captured_at DESC;

-- A handy slate view for the API (joins game + model + best quotes)
CREATE OR REPLACE VIEW game_slate AS
SELECT
  gf.game_id,
  gf.game_date,
  gf.home_team,
  gf.away_team,
  gp.p_home_win,
  gp.p_away_win,
  b_home.book AS best_home_book,
  b_home.american_odds AS best_home_american,
  b_home.decimal_odds AS best_home_decimal,
  b_away.book AS best_away_book,
  b_away.american_odds AS best_away_american,
  b_away.decimal_odds  AS best_away_decimal
FROM game_features gf
JOIN game_pricing gp ON gp.game_id = gf.game_id
LEFT JOIN best_moneyline_quotes b_home ON b_home.game_id = gf.game_id AND b_home.outcome = 'home'
LEFT JOIN best_moneyline_quotes b_away ON b_away.game_id = gf.game_id AND b_away.outcome = 'away';
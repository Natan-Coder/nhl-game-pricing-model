-- Minimal demo data for smoke-tests
INSERT INTO game_features (game_id, game_date, home_team, away_team, home_rest, away_rest, home_back_to_back, away_back_to_back, home_elo, away_elo)
VALUES (2025010101, CURRENT_DATE, 'BOS', 'MTL', 2, 2, FALSE, FALSE, 1550, 1500)
    ON CONFLICT (game_id) DO NOTHING;


INSERT INTO game_pricing (game_id, p_home_win, p_away_win, total_lambda, created_at)
VALUES (2025010101, 0.57, 0.43, 6.1, now())
    ON CONFLICT (game_id) DO NOTHING;


INSERT INTO odds_quotes (game_id, book, market, outcome, american_odds, line_number, captured_at)
VALUES
    (2025010101, 'DemoBook', 'moneyline', 'home', -120, NULL, now()),
    (2025010101, 'DemoBook', 'moneyline', 'away', +105, NULL, now())
    ON CONFLICT DO NOTHING;
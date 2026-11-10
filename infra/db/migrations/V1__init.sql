-- Raw odds quotes captured over time
CREATE TABLE IF NOT EXISTS odds_quotes (
  id BIGSERIAL PRIMARY KEY,
  game_id BIGINT NOT NULL,
  book TEXT NOT NULL,
  market TEXT NOT NULL, -- moneyline|total|puckline
  outcome TEXT NOT NULL, -- home|away|over|under|home-1.5|away+1.5
  american_odds INT NOT NULL,
  line_number NUMERIC, -- e.g., 6.5 for totals
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_odds_quotes_lookup ON odds_quotes (game_id, book, market, outcome);


-- Modeled features snapshot per game
CREATE TABLE IF NOT EXISTS game_features (
  game_id BIGINT PRIMARY KEY,
  game_date DATE NOT NULL,
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  home_goalie TEXT,
  away_goalie TEXT,
  home_rest INT,
  away_rest INT,
  home_back_to_back BOOLEAN,
  away_back_to_back BOOLEAN,
  home_xgf_60 NUMERIC,
  home_xga_60 NUMERIC,
  away_xgf_60 NUMERIC,
  away_xga_60 NUMERIC,
  home_pp_xg_rate NUMERIC,
  home_pk_xg_allowed NUMERIC,
  away_pp_xg_rate NUMERIC,
  away_pk_xg_allowed NUMERIC,
  home_elo NUMERIC,
  away_elo NUMERIC
);


-- Model outputs per game (probabilities & totals lambda)
CREATE TABLE IF NOT EXISTS game_pricing (
  game_id BIGINT PRIMARY KEY,
  p_home_win NUMERIC NOT NULL CHECK (p_home_win >= 0 AND p_home_win <= 1),
  p_away_win NUMERIC NOT NULL CHECK (p_away_win >= 0 AND p_away_win <= 1),
  total_lambda NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Edges computed vs market at a given time
CREATE TABLE IF NOT EXISTS edges (
  id BIGSERIAL PRIMARY KEY,
  game_id BIGINT NOT NULL,
  book TEXT NOT NULL,
  market TEXT NOT NULL,
  outcome TEXT NOT NULL,
  american_odds INT NOT NULL,
  implied_prob NUMERIC NOT NULL,
  model_prob NUMERIC NOT NULL,
  edge NUMERIC NOT NULL,
  kelly_fraction NUMERIC NOT NULL,
  bankroll NUMERIC NOT NULL,
  suggested_stake NUMERIC NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_edges_lookup ON edges (computed_at DESC, market, book);
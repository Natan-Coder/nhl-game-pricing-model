-- V14__elo_pricing_basics.sql

-- 1) Where we store final results (one row per finished game).
CREATE TABLE IF NOT EXISTS public.game_results (
  game_id            bigint PRIMARY KEY,
  game_date          date,
  home_team          text NOT NULL,
  away_team          text NOT NULL,
  home_goals         int  NOT NULL,
  away_goals         int  NOT NULL,
  decided_in_ot_so   boolean DEFAULT false,
  ingested_at        timestamptz DEFAULT now()
);

-- Helpful index for recent backfills
CREATE INDEX IF NOT EXISTS ix_game_results_date ON public.game_results (game_date);

-- 2) Team ratings (Elo)
CREATE TABLE IF NOT EXISTS public.team_ratings (
  team_abbr   text PRIMARY KEY,
  elo         numeric(10,4) NOT NULL,
  updated_at  timestamptz    NOT NULL DEFAULT now()
);

-- Seed all teams at 1500 if they don't exist
INSERT INTO public.team_ratings (team_abbr, elo)
SELECT t, 1500.0
FROM (VALUES
  ('ANA'),('ARI'),('BOS'),('BUF'),('CGY'),('CAR'),('CHI'),('COL'),
  ('CBJ'),('DAL'),('DET'),('EDM'),('FLA'),('LAK'),('MIN'),('MTL'),
  ('NSH'),('NJD'),('NYI'),('NYR'),('OTT'),('PHI'),('PIT'),('SJS'),
  ('SEA'),('STL'),('TBL'),('TOR'),('VAN'),('VGK'),('WSH'),('WPG')
) AS teams(t)
ON CONFLICT (team_abbr) DO NOTHING;

-- 3) Ledger so we update each finished game once
CREATE TABLE IF NOT EXISTS public.elo_training_ledger (
  game_id   bigint PRIMARY KEY,
  trained_at timestamptz NOT NULL DEFAULT now()
);

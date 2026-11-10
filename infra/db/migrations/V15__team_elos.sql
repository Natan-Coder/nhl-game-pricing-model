-- V15__team_elos.sql
-- Historical Elo store: one row per (team, updated_at)
CREATE TABLE IF NOT EXISTS public.team_elos (
  team_abbr   text        NOT NULL,
  elo         numeric(10,4) NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS ix_team_elos_team ON public.team_elos (team_abbr);
CREATE INDEX IF NOT EXISTS ix_team_elos_team_updated ON public.team_elos (team_abbr, updated_at DESC);
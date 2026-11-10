-- V16__seed_team_elos.sql
-- Seed a single baseline row per NHL team if table is empty.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.team_elos) THEN
    INSERT INTO public.team_elos (team_abbr, elo, updated_at) VALUES
      ('ANA',1500, now()), ('ARI',1500, now()), ('BOS',1500, now()), ('BUF',1500, now()),
      ('CGY',1500, now()), ('CAR',1500, now()), ('CHI',1500, now()), ('COL',1500, now()),
      ('CBJ',1500, now()), ('DAL',1500, now()), ('DET',1500, now()), ('EDM',1500, now()),
      ('FLA',1500, now()), ('LAK',1500, now()), ('MIN',1500, now()), ('MTL',1500, now()),
      ('NSH',1500, now()), ('NJD',1500, now()), ('NYI',1500, now()), ('NYR',1500, now()),
      ('OTT',1500, now()), ('PHI',1500, now()), ('PIT',1500, now()), ('SJS',1500, now()),
      ('SEA',1500, now()), ('STL',1500, now()), ('TBL',1500, now()), ('TOR',1500, now()),
      ('VAN',1500, now()), ('VGK',1500, now()), ('WSH',1500, now()), ('WPG',1500, now());
END IF;
END $$;
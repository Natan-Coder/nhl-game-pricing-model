-- V11: make schedule upsert-tolerant for NHL web API

-- 1) Add/ensure columns exist
DO $$
BEGIN
  -- timestamptz UTC start time
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='game_features'
      AND column_name='game_datetime_utc'
  ) THEN
    ALTER TABLE public.game_features
      ADD COLUMN game_datetime_utc timestamptz;
  END IF;

  -- venue (nullable)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='game_features'
      AND column_name='venue'
  ) THEN
    ALTER TABLE public.game_features
      ADD COLUMN venue text;
  END IF;

  -- game_type (nullable int, e.g., 1=pre, 2=reg, 3=playoffs)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='game_features'
      AND column_name='game_type'
  ) THEN
    ALTER TABLE public.game_features
      ADD COLUMN game_type integer;
  END IF;
END$$;

-- 2) Ensure a unique key/PK on game_id so UPSERT can target it
DO $$
BEGIN
  -- If there's no PK or unique on game_id, create a unique constraint
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.game_features'::regclass
      AND contype IN ('p','u')
      AND conkey = ARRAY[
        (SELECT attnum FROM pg_attribute
         WHERE attrelid='public.game_features'::regclass
           AND attname='game_id')
      ]
  ) THEN
    -- Try to promote to PK if table doesn’t already have one; otherwise add UNIQUE
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid = 'public.game_features'::regclass AND contype='p'
    ) THEN
      ALTER TABLE public.game_features
        ADD CONSTRAINT pk_game_features_game_id PRIMARY KEY (game_id);
    ELSE
      ALTER TABLE public.game_features
        ADD CONSTRAINT uq_game_features_game_id UNIQUE (game_id);
    END IF;
  END IF;
END$$;

-- 3) Helpful index for date queries (optional, idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
     WHERE schemaname='public' AND tablename='game_features' AND indexname='ix_game_features_game_date'
  ) THEN
    CREATE INDEX ix_game_features_game_date ON public.game_features (game_date);
  END IF;
END$$;
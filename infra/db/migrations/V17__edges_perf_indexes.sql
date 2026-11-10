-- Edges hot filters
create index if not exists ix_edges_recent on edges (computed_at desc);
create index if not exists ix_edges_game_market on edges (game_id, market, computed_at desc);

-- Quotes hot filters
create index if not exists ix_quotes_recent on odds_quotes (captured_at desc);
create index if not exists ix_quotes_game_market on odds_quotes (game_id, market, captured_at desc);

-- V18__mv_best_moneyline.sql
drop materialized view if exists mv_best_moneyline;
create materialized view mv_best_moneyline as
with latest as (
  select q.*
  from v_latest_quotes q
  where q.market = 'moneyline'
)
select l.game_id,
       l.outcome,
       -- pick best (highest) decimal odds == most favorable American
       first_value(l.book) over w as best_book,
    first_value(l.american_odds) over w as best_american_odds
from latest l
window w as (partition by l.game_id, l.outcome order by l.american_odds desc);
-- You can add unique index if you want one row per (game_id, outcome)

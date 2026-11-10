# PostgreSQL Optimization Plan - Future-Proofing Strategy

**Created:** April 19, 2026
**Current Database:** Supabase PostgreSQL 16
**Status:** Recommendations for Production Deployment

---

## Executive Summary

Your database is well-designed but will face scalability challenges as data grows. This plan addresses:
1. **Table partitioning** for multi-million row tables
2. **Materialized view automation** for real-time reporting
3. **Index optimization** for query performance
4. **Connection pooling** (already handled by Supabase)
5. **Monitoring & alerting** for proactive maintenance
6. **Data archival** for historical data management

**Priority Order:** High → Medium → Low
**Estimated Total Implementation:** 16-24 hours across 4-6 weeks

---

## Current State Assessment

### ✅ Strengths
- Using managed Supabase (automatic backups, high availability)
- PgBouncer connection pooling already configured
- Good index coverage on high-traffic queries
- Proper foreign key relationships
- TIMESTAMPTZ for all timestamps (timezone-aware)
- Migration versioning with Flyway

### ⚠️ Pain Points
- `odds_quotes` and `edges` tables growing unbounded (millions of rows)
- Materialized views require manual refresh
- No data archival strategy for old seasons
- Missing monitoring/alerting for query performance
- No query timeout protection
- Potential for stale data in views

### 📊 Growth Projections

| Table | Current Size | Growth Rate | 1 Year Projection |
|-------|-------------|-------------|-------------------|
| `odds_quotes` | ~2M rows | ~5k/day | ~4M rows |
| `edges` | ~3M rows | ~10k/day | ~6M rows |
| `bet_log` | ~500 rows | ~10/day | ~4k rows |
| `game_features` | ~4k rows | ~5/day | ~6k rows |
| `team_elo_history` | ~10k rows | ~30/day | ~20k rows |

**Storage Growth:** ~1-2 GB/year at current volume

---

## Optimization Roadmap

---

## 🔥 PRIORITY 1: Critical for Production (Week 1-2)

### 1.1 Table Partitioning for Time-Series Data

**Affected Tables:** `odds_quotes`, `edges`

**Problem:** Full table scans on multi-million row tables cause slow queries

**Solution:** Implement range partitioning by date

#### Implementation for `odds_quotes`

**Migration:** `V33__partition_odds_quotes.sql`

```sql
-- Step 1: Rename existing table
ALTER TABLE odds_quotes RENAME TO odds_quotes_old;

-- Step 2: Create partitioned table
CREATE TABLE odds_quotes (
  id BIGSERIAL,
  game_id BIGINT NOT NULL,
  book TEXT NOT NULL,
  market TEXT NOT NULL,
  outcome TEXT NOT NULL,
  american_odds INT NOT NULL,
  line_number NUMERIC,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (captured_at);

-- Step 3: Create partitions (monthly)
-- Current season (2025-26)
CREATE TABLE odds_quotes_2025_10 PARTITION OF odds_quotes
  FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE odds_quotes_2025_11 PARTITION OF odds_quotes
  FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE odds_quotes_2025_12 PARTITION OF odds_quotes
  FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
CREATE TABLE odds_quotes_2026_01 PARTITION OF odds_quotes
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE odds_quotes_2026_02 PARTITION OF odds_quotes
  FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE odds_quotes_2026_03 PARTITION OF odds_quotes
  FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE odds_quotes_2026_04 PARTITION OF odds_quotes
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Future partition (prevents insert failures)
CREATE TABLE odds_quotes_2026_05 PARTITION OF odds_quotes
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- Step 4: Copy data from old table
INSERT INTO odds_quotes SELECT * FROM odds_quotes_old;

-- Step 5: Recreate indexes on partitioned table
CREATE INDEX idx_odds_quotes_lookup ON odds_quotes (game_id, book, market, outcome);
CREATE INDEX idx_quotes_game ON odds_quotes (game_id, market, outcome, captured_at DESC);

-- Step 6: Drop old table (after verification)
-- DROP TABLE odds_quotes_old;
```

**Benefits:**
- Query performance: 5-10x faster for date-range queries
- Maintenance: Drop old partitions instead of DELETE (instant)
- Archival: Move old partitions to cold storage easily

**Maintenance Script:** `pipelines/maintenance/create_monthly_partitions.py`

```python
"""
Create next month's partition for odds_quotes and edges tables.
Run this monthly via cron or Supabase scheduler.
"""
from datetime import datetime, timedelta
from pipelines.common.db import connect
import os

def create_next_partition(table_name: str, start_date: datetime):
    """Create partition for next month."""
    end_date = start_date + timedelta(days=31)
    partition_name = f"{table_name}_{start_date.strftime('%Y_%m')}"

    sql = f"""
    CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF {table_name}
    FOR VALUES FROM ('{start_date.date()}') TO ('{end_date.date()}');
    """

    dsn = os.getenv('DATABASE_URL')
    with connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print(f"Created partition: {partition_name}")

if __name__ == '__main__':
    # Create partitions for next 3 months
    today = datetime.now()
    for i in range(1, 4):
        next_month = today + timedelta(days=30 * i)
        next_month = next_month.replace(day=1)
        create_next_partition('odds_quotes', next_month)
        create_next_partition('edges', next_month)
```

**Cron Job:** Run monthly
```bash
0 0 1 * * cd /path/to/project && python -m pipelines.maintenance.create_monthly_partitions
```

---

#### Implementation for `edges`

**Migration:** `V34__partition_edges.sql`

```sql
-- Same pattern as odds_quotes
ALTER TABLE edges RENAME TO edges_old;

CREATE TABLE edges (
  id BIGSERIAL,
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
) PARTITION BY RANGE (computed_at);

-- Create monthly partitions (same as odds_quotes)
-- ... (repeat partition creation)

-- Copy data
INSERT INTO edges SELECT * FROM edges_old;

-- Recreate indexes
CREATE INDEX idx_edges_lookup ON edges (computed_at DESC, market, book);
CREATE INDEX idx_edges_game ON edges (game_id, computed_at DESC);

-- Drop old table after verification
-- DROP TABLE edges_old;
```

**Estimated Time:** 4-6 hours
**Impact:** High - Prevents future query slowdowns

---

### 1.2 Materialized View Auto-Refresh

**Affected Views:** `strategy_performance`, `mv_best_moneyline`

**Problem:** Views show stale data unless manually refreshed

**Solution:** PostgreSQL function + scheduled refresh

**Migration:** `V35__mv_refresh_function.sql`

```sql
-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_best_moneyline;
  REFRESH MATERIALIZED VIEW CONCURRENTLY strategy_performance;

  RAISE NOTICE 'Materialized views refreshed at %', now();
END;
$$ LANGUAGE plpgsql;

-- For CONCURRENT refresh, views need unique indexes
CREATE UNIQUE INDEX IF NOT EXISTS mv_best_moneyline_uniq
  ON mv_best_moneyline (game_id, outcome);

CREATE UNIQUE INDEX IF NOT EXISTS strategy_performance_uniq
  ON strategy_performance (strategy_id);
```

**Supabase Cron Setup:**

Since Supabase supports `pg_cron` extension:

```sql
-- Enable pg_cron (run once via SQL editor in Supabase dashboard)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule refresh every 15 minutes
SELECT cron.schedule(
  'refresh-materialized-views',
  '*/15 * * * *',  -- Every 15 minutes
  'SELECT refresh_all_materialized_views();'
);

-- Verify scheduled job
SELECT * FROM cron.job;
```

**Alternative: Python Scheduler** (if pg_cron not available)

`pipelines/maintenance/refresh_views.py`

```python
"""Refresh materialized views. Run via cron every 15 minutes."""
from pipelines.common.db import connect
import os

dsn = os.getenv('DATABASE_URL')
with connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_best_moneyline;")
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY strategy_performance;")
    conn.commit()
print("Materialized views refreshed successfully")
```

**Cron Job:**
```bash
*/15 * * * * cd /path/to/project && python -m pipelines.maintenance.refresh_views
```

**Estimated Time:** 1-2 hours
**Impact:** Medium - Ensures real-time reporting accuracy

---

### 1.3 Query Timeout Protection

**Problem:** Long-running queries can block production workloads

**Solution:** Set statement timeouts globally and per-role

**Migration:** `V36__query_timeouts.sql`

```sql
-- Set default statement timeout to 30 seconds
ALTER DATABASE postgres SET statement_timeout = '30s';

-- For analytical queries, create separate role with higher timeout
CREATE ROLE analytics_user LOGIN PASSWORD 'secure_password_here';
GRANT CONNECT ON DATABASE postgres TO analytics_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_user;
ALTER ROLE analytics_user SET statement_timeout = '5min';

-- For application user (normal queries)
-- Assuming current user is 'postgres.tpsmibvlgalbuurplbhu' from docker-compose
ALTER ROLE "postgres.tpsmibvlgalbuurplbhu" SET statement_timeout = '10s';
```

**Python Connection Update:** `pipelines/common/db.py`

```python
# Add timeout override for specific operations
@contextmanager
def connect(dsn: str, timeout: int = None, **kwargs):
    """
    Connect to the database with optional connection parameters.
    timeout: statement timeout in seconds (overrides database default)
    """
    conn_params = {"prepare_threshold": None}
    conn_params.update(kwargs)
    conn = psycopg.connect(dsn, **conn_params)
    try:
        if timeout:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = '{timeout}s'")
        yield conn
    finally:
        conn.close()
```

**Usage:**
```python
# Fast queries (default 10s timeout from database)
with connect(dsn) as conn:
    ...

# Long-running backtest (override to 5 minutes)
with connect(dsn, timeout=300) as conn:
    ...
```

**Estimated Time:** 1 hour
**Impact:** High - Prevents runaway queries

---

## 🟡 PRIORITY 2: Performance Optimization (Week 3-4)

### 2.1 Index Optimization

**Goal:** Add missing indexes and remove unused ones

**Analysis Query:** Run this to find missing indexes

```sql
-- Find tables with sequential scans (candidates for indexing)
SELECT
  schemaname,
  tablename,
  seq_scan,
  seq_tup_read,
  idx_scan,
  seq_tup_read / NULLIF(seq_scan, 0) as avg_seq_read
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 20;

-- Find unused indexes (candidates for removal)
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan,
  pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE 'pg_toast%'
ORDER BY pg_relation_size(indexrelid) DESC;
```

**Recommended New Indexes:**

**Migration:** `V37__optimize_indexes.sql`

```sql
-- 1. Bet log: Query by game_id + status (for result reconciliation)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bet_log_game_status
  ON bet_log (game_id, bet_status)
  WHERE bet_status = 'pending';

-- 2. Odds quotes: Filter by market + captured_at (for latest quotes)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_odds_quotes_market_time
  ON odds_quotes (market, captured_at DESC);

-- 3. Edges: Filter by edge threshold (for bet selection)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_threshold
  ON edges (edge DESC, kelly_fraction DESC)
  WHERE edge >= 0.03;

-- 4. Game features: Lookup by date range (for backtesting)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_game_features_date
  ON game_features (game_date);

-- 5. Team ELO history: Composite for backtesting queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_team_elo_lookup
  ON team_elo_history (team_code, game_date DESC);

-- 6. Bet log: Analyze by date range
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bet_log_placed_date
  ON bet_log (DATE(bet_placed_at), strategy_id);
```

**Indexes to Consider Removing** (after verification with query logs)

```sql
-- Check if idx_odds_quotes_lookup is redundant with idx_quotes_game
-- If idx_quotes_game covers all queries, drop the other:
-- DROP INDEX CONCURRENTLY idx_odds_quotes_lookup;
```

**Estimated Time:** 2-3 hours
**Impact:** Medium - 20-40% query speedup

---

### 2.2 Data Archival Strategy

**Problem:** Old seasons slow down queries and waste storage

**Solution:** Archive completed seasons to separate tables

**Migration:** `V38__archive_tables.sql`

```sql
-- Create archive schema
CREATE SCHEMA IF NOT EXISTS archive;

-- Archive template for odds_quotes
CREATE TABLE IF NOT EXISTS archive.odds_quotes_2023_24 (
  LIKE odds_quotes INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS archive.odds_quotes_2024_25 (
  LIKE odds_quotes INCLUDING ALL
);

-- Archive template for edges
CREATE TABLE IF NOT EXISTS archive.edges_2023_24 (
  LIKE edges INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS archive.edges_2024_25 (
  LIKE edges INCLUDING ALL
);
```

**Archival Script:** `pipelines/maintenance/archive_season.py`

```python
"""
Archive completed season data to archive schema.
Run manually at end of season.
"""
from pipelines.common.db import connect
import os

def archive_season(season: str, start_date: str, end_date: str):
    """
    Archive data for a completed season.
    Example: archive_season('2024_25', '2024-10-01', '2025-04-30')
    """
    dsn = os.getenv('DATABASE_URL')

    with connect(dsn) as conn:
        with conn.cursor() as cur:
            # Archive odds_quotes
            cur.execute(f"""
                INSERT INTO archive.odds_quotes_{season}
                SELECT * FROM odds_quotes
                WHERE captured_at >= %s AND captured_at < %s;
            """, (start_date, end_date))

            # Archive edges
            cur.execute(f"""
                INSERT INTO archive.edges_{season}
                SELECT * FROM edges
                WHERE computed_at >= %s AND computed_at < %s;
            """, (start_date, end_date))

            # Delete from main tables (or use DROP PARTITION if partitioned)
            cur.execute("""
                DELETE FROM odds_quotes
                WHERE captured_at >= %s AND captured_at < %s;
            """, (start_date, end_date))

            cur.execute("""
                DELETE FROM edges
                WHERE computed_at >= %s AND computed_at < %s;
            """, (start_date, end_date))

        conn.commit()

    print(f"Season {season} archived successfully")

if __name__ == '__main__':
    # Example: Archive 2024-25 season after playoffs end
    archive_season('2024_25', '2024-10-01', '2025-06-30')
```

**Best Practice:** Run after Stanley Cup Finals (late June)

**Estimated Time:** 2 hours
**Impact:** Medium - Keeps production tables lean

---

### 2.3 Vacuum & Analyze Automation

**Problem:** PostgreSQL needs regular maintenance for optimal performance

**Solution:** Scheduled VACUUM ANALYZE jobs

**Supabase Cron Setup:**

```sql
-- Daily vacuum analyze on large tables
SELECT cron.schedule(
  'vacuum-large-tables',
  '0 2 * * *',  -- 2 AM daily
  $$
    VACUUM ANALYZE odds_quotes;
    VACUUM ANALYZE edges;
    VACUUM ANALYZE bet_log;
  $$
);

-- Weekly full vacuum on smaller tables
SELECT cron.schedule(
  'vacuum-small-tables',
  '0 3 * * 0',  -- 3 AM Sunday
  $$
    VACUUM FULL ANALYZE game_features;
    VACUUM FULL ANALYZE team_elo_history;
    VACUUM FULL ANALYZE betting_strategies;
  $$
);
```

**Estimated Time:** 30 minutes
**Impact:** Low - Supabase handles this automatically, but explicit control is better

---

## 🔵 PRIORITY 3: Monitoring & Observability (Week 5-6)

### 3.1 Query Performance Monitoring

**Install pg_stat_statements extension:**

```sql
-- Enable extension (run once)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Query to find slowest queries
SELECT
  query,
  calls,
  total_exec_time,
  mean_exec_time,
  max_exec_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC
LIMIT 20;
```

**Create monitoring view:**

**Migration:** `V39__monitoring_views.sql`

```sql
CREATE OR REPLACE VIEW v_slow_queries AS
SELECT
  query,
  calls,
  ROUND(total_exec_time::numeric, 2) as total_time_ms,
  ROUND(mean_exec_time::numeric, 2) as avg_time_ms,
  ROUND(max_exec_time::numeric, 2) as max_time_ms,
  ROUND((100 * total_exec_time / SUM(total_exec_time) OVER ())::numeric, 2) as pct_total_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
  AND mean_exec_time > 100  -- Over 100ms average
ORDER BY mean_exec_time DESC;

-- View for table bloat
CREATE OR REPLACE VIEW v_table_bloat AS
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
  pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as indexes_size,
  n_tup_ins as inserts,
  n_tup_upd as updates,
  n_tup_del as deletes,
  n_live_tup as live_rows,
  n_dead_tup as dead_rows,
  ROUND((n_dead_tup::float / NULLIF(n_live_tup, 0) * 100)::numeric, 2) as dead_row_pct
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Monitoring Script:** `pipelines/maintenance/db_health_check.py`

```python
"""
Database health check - run daily and alert on issues.
"""
from pipelines.common.db import connect
import os
import logging

log = logging.getLogger(__name__)

def check_database_health():
    """Run health checks and log warnings."""
    dsn = os.getenv('DATABASE_URL')

    with connect(dsn) as conn:
        with conn.cursor() as cur:
            # Check 1: Slow queries
            cur.execute("""
                SELECT COUNT(*) FROM v_slow_queries
                WHERE avg_time_ms > 500;
            """)
            slow_count = cur.fetchone()[0]
            if slow_count > 5:
                log.warning(f"Found {slow_count} slow queries (>500ms avg)")

            # Check 2: Table bloat
            cur.execute("""
                SELECT tablename, dead_row_pct
                FROM v_table_bloat
                WHERE dead_row_pct > 20;
            """)
            bloated_tables = cur.fetchall()
            if bloated_tables:
                for table, pct in bloated_tables:
                    log.warning(f"Table {table} has {pct}% dead rows - consider VACUUM")

            # Check 3: Disk usage
            cur.execute("""
                SELECT pg_size_pretty(pg_database_size('postgres'));
            """)
            db_size = cur.fetchone()[0]
            log.info(f"Database size: {db_size}")

            # Check 4: Materialized view staleness
            cur.execute("""
                SELECT
                    schemaname,
                    matviewname,
                    last_vacuum,
                    EXTRACT(EPOCH FROM (now() - last_vacuum))/60 as minutes_since_refresh
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                  AND relname LIKE 'mv_%' OR relname LIKE '%_performance';
            """)
            stale_views = cur.fetchall()
            for schema, view, last_refresh, minutes in stale_views:
                if minutes and minutes > 60:
                    log.warning(f"Materialized view {view} not refreshed in {minutes:.0f} minutes")

    print("Database health check completed")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    check_database_health()
```

**Cron Job:** Daily health check
```bash
0 6 * * * cd /path/to/project && python -m pipelines.maintenance.db_health_check
```

**Estimated Time:** 3-4 hours
**Impact:** Medium - Proactive issue detection

---

### 3.2 Alerting Setup

**Problem:** Database issues go unnoticed until critical

**Solution:** Integrate with alerting system

**Options:**

1. **Supabase Dashboard Alerts** (if available in your plan)
2. **External Monitoring:** Datadog, New Relic, Sentry
3. **Custom Script:** Email/Slack alerts

**Example: Slack Alerting Script**

`pipelines/alerts/db_alerts.py`

```python
"""
Send Slack alerts for database issues.
Requires SLACK_WEBHOOK_URL env var.
"""
import requests
import os
from pipelines.maintenance.db_health_check import check_database_health

SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK_URL')

def send_slack_alert(message: str):
    """Send alert to Slack."""
    if not SLACK_WEBHOOK:
        print(f"ALERT: {message}")
        return

    payload = {
        "text": f"🚨 Database Alert: {message}",
        "username": "NHL Betting DB Monitor"
    }
    requests.post(SLACK_WEBHOOK, json=payload)

# Integration with health check
# Modify db_health_check.py to call send_slack_alert() on warnings
```

**Estimated Time:** 2 hours
**Impact:** Low - Peace of mind

---

## 📋 Implementation Checklist

### Week 1-2: Critical Items
- [ ] Implement table partitioning for `odds_quotes` (V33)
- [ ] Implement table partitioning for `edges` (V34)
- [ ] Create partition management script
- [ ] Set up materialized view auto-refresh (V35)
- [ ] Configure query timeouts (V36)
- [ ] Test partition performance vs non-partitioned

### Week 3-4: Performance
- [ ] Add recommended indexes (V37)
- [ ] Analyze index usage after 1 week
- [ ] Create archive schema (V38)
- [ ] Set up vacuum automation
- [ ] Document archival process

### Week 5-6: Monitoring
- [ ] Enable pg_stat_statements
- [ ] Create monitoring views (V39)
- [ ] Set up daily health check script
- [ ] Configure alerting (Slack/email)
- [ ] Create runbook for common issues

---

## 🔧 Maintenance Playbook

### Daily Tasks (Automated)
- ✅ Materialized view refresh (every 15 min via pg_cron)
- ✅ Database health check (6 AM via cron)
- ✅ Vacuum analyze large tables (2 AM via pg_cron)

### Weekly Tasks (Automated)
- ✅ Full vacuum on small tables (Sunday 3 AM)
- ✅ Review slow query log
- ✅ Check disk usage trends

### Monthly Tasks (Manual)
- [ ] Create next month's partitions (or automate)
- [ ] Review index usage and remove unused indexes
- [ ] Check for schema migration opportunities
- [ ] Update documentation

### Seasonal Tasks (Manual)
- [ ] Archive completed season (June, after playoffs)
- [ ] Analyze season performance and optimize
- [ ] Plan schema changes for next season

---

## 📊 Success Metrics

Track these metrics before and after optimization:

| Metric | Before | Target | How to Measure |
|--------|--------|--------|----------------|
| Avg query time (bet selection) | ? | <100ms | `SELECT mean_exec_time FROM pg_stat_statements WHERE query LIKE '%actionable_edges%'` |
| Avg query time (odds lookup) | ? | <50ms | `SELECT mean_exec_time FROM pg_stat_statements WHERE query LIKE '%latest_quotes%'` |
| Table scan ratio | ? | <10% | `SELECT SUM(seq_scan) / SUM(idx_scan) FROM pg_stat_user_tables` |
| Materialized view staleness | Manual | <15 min | Check last refresh timestamp |
| Database size | ? | Track growth | `SELECT pg_size_pretty(pg_database_size('postgres'))` |
| Dead row percentage | ? | <5% | `SELECT AVG(dead_row_pct) FROM v_table_bloat` |

---

## 🚨 Rollback Plan

If optimization causes issues:

### Rollback Partitioning
```sql
-- If partitioned table has issues, revert to old table
DROP TABLE odds_quotes;
ALTER TABLE odds_quotes_old RENAME TO odds_quotes;
```

### Rollback Index Changes
```sql
-- Drop problematic new index
DROP INDEX CONCURRENTLY idx_edges_threshold;
```

### Rollback Timeouts
```sql
-- Remove statement timeout
ALTER DATABASE postgres RESET statement_timeout;
```

---

## 💰 Cost Considerations

**Supabase Pricing Impact:**

1. **Storage:** Partitioning + archival keeps storage minimal
2. **Compute:** Faster queries = less compute time
3. **Bandwidth:** No change (same data volume)

**Estimated Savings:** $10-30/month if archival prevents next tier upgrade

---

## 🎓 Learning Resources

- [PostgreSQL Partitioning Docs](https://www.postgresql.org/docs/16/ddl-partitioning.html)
- [Supabase pg_cron Guide](https://supabase.com/docs/guides/database/extensions/pg_cron)
- [Index Optimization Best Practices](https://www.postgresql.org/docs/16/indexes.html)
- [Query Performance Tuning](https://www.postgresql.org/docs/16/performance-tips.html)

---

## 📝 Notes

- **Supabase Connection Pooling:** Already handled via PgBouncer (port 6543). Your connection string uses `pooler.supabase.com:6543` which is optimal.
- **Migration Testing:** Test all migrations on staging database first (use Flyway's `baseline` feature)
- **Backup Before Changes:** Supabase has automatic backups, but take manual snapshot before major changes

---

**Next Review:** After 3 months of live production (July 2026)
**Owner:** [Your Name]
**Status:** 🟢 Ready for Implementation

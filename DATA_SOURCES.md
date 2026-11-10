# NHL Betting Model - Data Sources Reference

**Date:** March 22, 2026
**Purpose:** Document all available data sources for model features

---

## Current Data Sources (Already Integrated)

### ✅ NHL API (Official)
- **URL:** https://api-web.nhle.com/v1/
- **Data:** Game results, scores, schedules, team stats, basic player stats
- **Cost:** Free
- **Status:** Already integrated in `pipelines/etl/`
- **Quality:** High (official source)

### ✅ Goalie Stats
- **Source:** NHL API
- **Data:** Save percentage, games played
- **Status:** Integrated but only 18.7% coverage (739/3,946 games)
- **Action Needed:** Backfill missing games

---

## New Data Sources Needed

### 🔴 PRIORITY 1: Injuries Data

**Why Critical:** Star player injuries have HUGE impact on game outcomes (estimated +5-10% win probability swing)

#### Option A: BALLDONTLIE NHL API (RECOMMENDED)
- **URL:** https://api.balldontlie.io/nhl/v1/player_injuries
- **Endpoint:** `GET https://api.balldontlie.io/nhl/v1/player_injuries`
- **Cost:** Free tier available (requires API key)
- **Data:** Currently injured players, injury type, status (day-to-day, IR, etc.)
- **Update Frequency:** Daily
- **Pros:**
  - Free tier available
  - Clean API with JSON responses
  - Actively maintained (updated for 2025-26 season)
- **Cons:**
  - May have rate limits on free tier
  - Historical injury data unclear
- **Integration Effort:** Medium (need to build new pipeline)

#### Option B: Sportradar NHL API
- **URL:** https://developer.sportradar.com/ice-hockey/reference/nhl-injuries
- **Endpoint:** `https://api.sportradar.us/nhl/{access_level}/v6/en/league/injuries.json?api_key={key}`
- **Cost:** PAID (likely $$$)
- **Data:** All active player injuries for all teams
- **Pros:**
  - Enterprise-grade reliability
  - Comprehensive coverage
  - Historical data likely available
- **Cons:**
  - Expensive (for hobby project)
  - Overkill for our needs
- **Integration Effort:** Medium

#### Option C: Hockey-Reference Web Scraping
- **URL:** https://www.hockey-reference.com/friv/injuries.cgi
- **Data:** Current injuries, day-to-day status
- **Cost:** Free
- **Pros:**
  - Free
  - Human-readable format
- **Cons:**
  - Web scraping is fragile (breaks if site changes)
  - Against ToS potentially
  - No historical data API
  - Update frequency unclear
- **Integration Effort:** High (need to build scraper + maintain)

**RECOMMENDATION:** Start with BALLDONTLIE API (free), upgrade to Sportradar only if needed

---

### 🟡 PRIORITY 2: Line Combinations

**Why Valuable:** Top line chemistry matters, especially vs defensive matchups

#### Option A: Daily Faceoff (Web Scraping)
- **URL:** https://www.dailyfaceoff.com/teams
- **Data:** Forward lines, defensive pairings, PP units, starting goalies
- **Cost:** Free
- **Update Frequency:** Daily, updated close to game time
- **Pros:**
  - Most comprehensive line data
  - Most cited source by analysts
  - Updated regularly
- **Cons:**
  - No API (need to scrape)
  - Web scraping is fragile
  - Legally gray area
- **Integration Effort:** High (build scraper)

#### Option B: Puckpedia
- **URL:** https://puckpedia.com/lineups
- **Data:** Starting lineups, depth charts, special teams
- **Cost:** Free
- **Pros:**
  - Clean, structured format
  - Updated daily throughout season
- **Cons:**
  - No API (need to scrape)
  - Less comprehensive than Daily Faceoff
- **Integration Effort:** High (build scraper)

#### Option C: NHL API (Official - Limited)
- **Data:** Game rosters (who played), but not projected lines
- **Pros:**
  - Official source
  - Reliable API
- **Cons:**
  - Only shows who played AFTER game
  - No pre-game line projections
  - Not useful for betting (need data before game)
- **Integration Effort:** Low (but limited value)

**RECOMMENDATION:**
1. Start WITHOUT line combinations (not worth scraping complexity yet)
2. Add later if model shows promise
3. Alternative: Use player-level stats aggregated to team (see below)

---

### 🟢 PRIORITY 3: Advanced Stats (Corsi, xGoals, etc.)

**Why Valuable:** Better measure of team quality than W-L record

#### Option A: NHL API (Official - NEW Edge Stats)
- **URL:** NHL API with new query builder
- **Data:** Advanced stats including Expected Goals (xG), shot attempts, etc.
- **Cost:** Free
- **Pros:**
  - Official source
  - Free
  - Programmatic access
  - Updated for 2025-26 season
- **Cons:**
  - Documentation can be unclear
  - May require some reverse engineering
- **Integration Effort:** Medium
- **Status:** RECOMMENDED - use this first

#### Option B: Natural Stat Trick (Manual Download)
- **URL:** https://www.naturalstattrick.com/
- **Data:** Corsi, Fenwick, xGoals, HDSC (High Danger Scoring Chances), etc.
- **Cost:** Free
- **Format:** CSV download (manual)
- **Pros:**
  - Very comprehensive advanced stats
  - Cleaned/validated data
  - Trusted by analytics community
- **Cons:**
  - NO API - must manually download CSVs
  - Data is sourced from NHL API anyway (we can get it ourselves)
  - Manual process doesn't scale
- **Integration Effort:** Low (one-time download) but manual
- **Use Case:** One-time backfill for historical data

#### Option C: MoneyPuck
- **URL:** http://moneypuck.com/data.htm
- **Data:** xGoals, player ratings, team stats
- **Cost:** Free
- **Format:** CSV download
- **Pros:**
  - Free
  - Good xGoals models
  - CSV download available
- **Cons:**
  - No API
  - Manual download process
  - Less comprehensive than Natural Stat Trick
- **Integration Effort:** Low (one-time) but manual

**RECOMMENDATION:**
1. Use NHL API Edge Stats for real-time data
2. Backfill historical data (2023-2025) from Natural Stat Trick CSVs (one-time)
3. Automate ongoing collection from NHL API

---

### 🟢 PRIORITY 4: Complete Goalie Coverage

**Current Status:** Only 739/3,946 games (18.7%) have goalie data

**Solution:** Backfill using NHL API
- **Endpoint:** Game rosters show starting goalies
- **Data Available:** 2023-2025 seasons should all be available
- **Effort:** Medium (build backfill script)
- **Impact:** HIGH - goalie feature showed +1.06% accuracy improvement

**Action:** Build `backfill_goalie_data.py` to fill gaps in 2023-2025 data

---

## Feature Priority Matrix

Based on expected impact vs implementation effort:

| Feature | Expected Impact | Implementation Effort | Priority | Start When |
|---------|----------------|----------------------|----------|-----------|
| **Injuries** | Very High (+5-10%) | Medium | 🔴 P1 | Phase 1 |
| **Complete Goalie Data** | High (+1%) | Medium | 🔴 P1 | Phase 1 |
| **Advanced Stats (xG, Corsi)** | Medium (+2-3%) | Medium | 🟡 P2 | Phase 1 |
| **Rest/B2B (we have this)** | Low (+0.5%) | Done ✅ | - | - |
| **Line Combinations** | Medium (+1-2%) | High (scraping) | 🟢 P3 | Phase 2 (if needed) |
| **Player Impact (WAR, etc.)** | Medium-High (+2-4%) | High | 🟢 P3 | Phase 2 |
| **Historical H2H** | Low (+0.5%) | Low | 🟢 P3 | Phase 2 (if needed) |
| **Betting Line Movement** | Medium (+1-2%) | High | 🟢 P3 | Phase 3 (nice-to-have) |

---

## Implementation Roadmap

### Phase 1: Data Engineering (Weeks 1-4)

**Week 1-2: Goalie Data Backfill**
- [ ] Build `backfill_goalie_data.py`
- [ ] Backfill 2023-2025 games (2,607 missing games)
- [ ] Verify coverage improves from 18.7% → ~90%+

**Week 3: Injuries Integration**
- [ ] Sign up for BALLDONTLIE API (free tier)
- [ ] Build `ingest_injuries.py` pipeline
- [ ] Create `player_injuries` table
- [ ] Backfill current season injuries
- [ ] Research historical injury data availability

**Week 4: Advanced Stats**
- [ ] Download Natural Stat Trick CSVs (2023-2025)
- [ ] Build `ingest_advanced_stats.py` to load CSVs
- [ ] Create `team_advanced_stats` table
- [ ] Build NHL API Edge Stats scraper for ongoing data
- [ ] Verify data matches Natural Stat Trick (validation)

### Phase 2: Optional Features (Weeks 5-8, if needed)

**Only if Phase 1 model shows promise:**
- [ ] Research line combinations scraping (Daily Faceoff)
- [ ] Build player-level stats aggregation
- [ ] Add travel distance calculations
- [ ] Add schedule density metrics

---

## Data Quality Checklist

For EACH new data source, verify:

- [ ] **Availability:** Can we get historical data for 2023-2025?
- [ ] **Coverage:** Does it cover all teams/games?
- [ ] **Timeliness:** Updated before game start time?
- [ ] **Reliability:** Has it failed/been down recently?
- [ ] **Cost:** Free tier sufficient? What are limits?
- [ ] **Legal:** Are we allowed to use this data?
- [ ] **Format:** JSON/CSV/API or web scraping needed?
- [ ] **Documentation:** Is there clear documentation?

---

## API Keys & Credentials

**Track API keys here:**

| Service | API Key Status | Rate Limits | Cost |
|---------|---------------|-------------|------|
| NHL API (Official) | No key needed | Unknown | Free |
| BALLDONTLIE | Need to sign up | TBD | Free tier |
| Sportradar | Not using | - | $$$ |

---

## Data Storage Strategy

### Tables to Create

```sql
-- Injuries tracking
CREATE TABLE player_injuries (
    player_id INT,
    player_name VARCHAR(100),
    team_id INT,
    injury_type VARCHAR(50),
    status VARCHAR(20),  -- 'day-to-day', 'IR', 'LTIR', 'out'
    date_injured DATE,
    date_returned DATE,
    games_missed INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Advanced team stats (per game)
CREATE TABLE team_advanced_stats (
    game_id BIGINT,
    team_id INT,
    corsi_for INT,
    corsi_against INT,
    fenwick_for INT,
    fenwick_against INT,
    xgoals_for DECIMAL(4,2),
    xgoals_against DECIMAL(4,2),
    high_danger_chances INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Line combinations (if we add later)
CREATE TABLE line_combinations (
    game_id BIGINT,
    team_id INT,
    line_number INT,  -- 1, 2, 3, 4
    left_wing_id INT,
    center_id INT,
    right_wing_id INT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Risks & Mitigation

### Risk 1: API Rate Limits
- **Mitigation:** Cache data aggressively, only fetch new data
- **Mitigation:** Use multiple sources as backup

### Risk 2: Historical Data Unavailable
- **Mitigation:** Start with current season, expand backwards if possible
- **Mitigation:** Some features (injuries) may only work going forward

### Risk 3: Data Quality Issues
- **Mitigation:** Validate new data against known good sources
- **Mitigation:** Add data quality checks to pipeline
- **Mitigation:** Alert on anomalies (e.g., entire team injured)

### Risk 4: Web Scraping Breaks
- **Mitigation:** Avoid web scraping where possible
- **Mitigation:** Build graceful fallbacks (use yesterday's lines if scraper fails)
- **Mitigation:** Monitor scraper health daily

---

## Next Steps

**This Week:**
1. Sign up for BALLDONTLIE API
2. Build goalie backfill script
3. Test NHL API Edge Stats access

**Next 2 Weeks:**
1. Implement injuries pipeline
2. Backfill advanced stats from Natural Stat Trick
3. Validate data quality

**Month 2:**
1. Build features from new data sources
2. Test feature impact on model accuracy
3. Decide if line combinations worth the effort

---

**Last Updated:** March 22, 2026

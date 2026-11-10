# Other Prediction Model Opportunities

**Date:** June 25, 2026
**Context:** After completing NHL betting model Phase 1 and investigating Phase 2
**Purpose:** Evaluate other prediction opportunities based on lessons learned

---

## Executive Summary

After successfully building an NHL betting model (Phase 1: 54.98% accuracy, 4.03% calibration) and investigating why Phase 2 features failed, we've learned valuable lessons about:
- Market efficiency
- Data quality requirements
- Feature engineering challenges
- The importance of calibration over accuracy
- How league structure affects predictability

**Key Insight:** Not all prediction problems are created equal. Success depends on:
1. **Market inefficiency** - Where are bookmakers/forecasters weak?
2. **Data availability** - Can you access better data than the market?
3. **Structural predictability** - Does the domain have enough signal?
4. **Calibration feasibility** - Can you generate well-calibrated probabilities?

This document evaluates opportunities in:
- Other sports
- Esports
- Financial markets
- Non-sports predictions
- Alternative NHL betting markets

---

## Lessons Learned from NHL Project

### What Worked

1. **ELO ratings** - Simple, effective team strength tracking
2. **Platt scaling** - Critical for well-calibrated probabilities
3. **Kelly criterion** - Optimal bet sizing
4. **Paper trading** - Safe validation before real money
5. **Temporal data splitting** - Proper train/val/test methodology
6. **Calibration focus** - More important than accuracy for betting

### What Didn't Work

1. **Rest days feature** - NHL scheduling already balanced (correlation -0.0246)
2. **Season-level goalie GAA** - Too coarse, needs game-by-game data
3. **Adding weak features** - Degraded calibration from 4.03% to 9.13%
4. **Fighting compression** - Better to accept narrow probabilities than force wider range
5. **Public data assumptions** - Markets price in obvious information

### Critical Success Factors

**For any prediction model to be profitable:**

1. **Edge exists** - You must know something the market doesn't
2. **Calibration quality** - Need accurate probability estimates, not just directional picks
3. **Sample size** - Need enough bets to overcome variance
4. **Bankroll management** - Kelly criterion or conservative sizing
5. **Discipline** - Only bet when edge exists, avoid tilt

---

## Evaluation Framework

For each opportunity, we'll evaluate:

### 1. Predictability (1-10)
- **10 = High:** Clear patterns, stable relationships, low variance
- **5 = Medium:** Some signal but high noise
- **1 = Low:** Random/chaotic, near-impossible to predict

### 2. Market Efficiency (1-10)
- **10 = Very inefficient:** Amateur bookmaking, obvious edges
- **5 = Moderate:** Some inefficiencies exploitable
- **1 = Very efficient:** Sharp bettors, no edges remain

### 3. Data Quality (1-10)
- **10 = Excellent:** Abundant, clean, historical data available
- **5 = Moderate:** Some data but incomplete or noisy
- **1 = Poor:** Little data, unreliable, expensive

### 4. Technical Difficulty (1-10)
- **10 = Very hard:** Complex modeling, advanced techniques needed
- **5 = Moderate:** Standard ML, some domain knowledge
- **1 = Easy:** Simple models work, straightforward implementation

### 5. ROI Potential (1-10)
- **10 = Excellent:** High edges, frequent opportunities
- **5 = Moderate:** Small edges, occasional opportunities
- **1 = Poor:** Minimal/no edges, not worth effort

---

## Sports Betting Opportunities

### 1. NBA (Basketball)

**Overview:** High-scoring, star-driven league with 82-game seasons.

**Pros:**
- More predictable than NHL (higher win % variance)
- Star players have outsized impact (easier to model)
- Abundant public data (stats, injuries, lineups)
- Less parity than NHL (tanking teams, superteams)

**Cons:**
- Very efficient betting markets (lots of sharp bettors)
- Load management complicates predictions
- Playoff seeding creates strategic tanking
- Injuries common and impactful

**Evaluation:**
- Predictability: 7/10 (star power reduces variance)
- Market Efficiency: 3/10 (very efficient)
- Data Quality: 9/10 (excellent public data)
- Technical Difficulty: 6/10 (need player-level models)
- ROI Potential: 5/10 (edges exist but small)

**Recommendation:** Worth exploring, especially:
- Player props (less efficient than game outcomes)
- In-game live betting (high variance, market slower to adjust)
- G-League or international leagues (less efficient markets)

**Lessons from NHL:** NBA likely has better probability discrimination (40-60% vs NHL's 47-54%) due to star power and less parity. Could achieve wider probability ranges with proper features.

---

### 2. NFL (American Football)

**Overview:** 17-game season, high variance sport, weekly betting cycles.

**Pros:**
- Moderate predictability (better than NHL, worse than NBA)
- Weekly schedule allows deep analysis per game
- Injuries and matchups heavily covered
- Point spread betting well-established

**Cons:**
- Only 17 games per season (small sample size)
- High variance (any team can win on given Sunday)
- Very efficient markets (massive betting volume)
- Injury impact huge but unpredictable

**Evaluation:**
- Predictability: 6/10 (moderate variance)
- Market Efficiency: 2/10 (very efficient, huge volume)
- Data Quality: 8/10 (good historical data)
- Technical Difficulty: 7/10 (complex matchup modeling)
- ROI Potential: 4/10 (edges tiny, market very sharp)

**Recommendation:** Not recommended unless:
- You have proprietary data (player tracking, advanced analytics)
- Focus on props/totals instead of spreads
- Target lower-tier games with less betting volume

**Lessons from NHL:** Small sample size (17 games) means high variance. Need very accurate calibration to overcome. Market efficiency likely makes this harder than NHL.

---

### 3. MLB (Baseball)

**Overview:** 162-game season, individual pitcher matchups critical.

**Pros:**
- Huge sample size (162 games per team)
- Pitcher vs batter matchups rich with data
- Sabermetrics well-developed (FIP, xWOBA, etc.)
- Daily betting opportunities

**Cons:**
- High variance within games (one swing changes outcome)
- Weather impact significant (wind, temperature)
- Bullpen usage unpredictable
- Public sabermetrics already priced into lines

**Evaluation:**
- Predictability: 5/10 (high variance despite stats)
- Market Efficiency: 4/10 (moderately efficient)
- Data Quality: 10/10 (best public data of any sport)
- Technical Difficulty: 7/10 (need advanced metrics knowledge)
- ROI Potential: 6/10 (edges exist, especially totals)

**Recommendation:** Moderate opportunity, especially:
- Totals (over/under) - weather + pitcher + ballpark model
- First 5 innings (removes bullpen uncertainty)
- Run line instead of moneyline

**Lessons from NHL:** Similar calibration challenges (50/50 games common). But better data quality might enable better features than NHL.

---

### 4. Soccer (Football)

**Overview:** Global sport, diverse leagues with varying competitiveness.

**Pros:**
- Many leagues to choose from (top 5 + lower tiers)
- International leagues less efficient than US sports
- Expected goals (xG) models well-established
- Draw option creates betting complexity

**Cons:**
- Low-scoring (high variance in individual games)
- Three-way betting (win/loss/draw) more complex
- Injury news unreliable outside top leagues
- Asian markets very sharp (European less so)

**Evaluation:**
- Predictability: 5/10 (low-scoring increases variance)
- Market Efficiency: 6/10 (varies by league - EPL efficient, lower leagues not)
- Data Quality: 7/10 (good for top leagues, poor for lower)
- Technical Difficulty: 6/10 (xG models + three-way outcomes)
- ROI Potential: 7/10 (lower leagues have inefficiencies)

**Recommendation:** Good opportunity if:
- Focus on lower-tier leagues (less efficient)
- Specialize in specific league (build expertise)
- Use xG data for totals betting
- Avoid EPL/La Liga (too efficient)

**Lessons from NHL:** Lower-tier soccer leagues might have better inefficiencies than top-tier NHL. Worth exploring League One, Championship, etc.

---

### 5. College Sports (NCAA Basketball/Football)

**Overview:** Amateur athletes, thousands of games, high variance.

**Pros:**
- Many games (300+ D1 basketball teams)
- Lower-tier conferences less efficient
- Emotional betting (homers overvalue favorites)
- Public data improving (KenPom, etc.)

**Cons:**
- Amateur athletes (high variance)
- Injuries/suspensions common, poorly reported
- Transfer portal creates roster instability
- Some conferences have terrible data

**Evaluation:**
- Predictability: 4/10 (amateur variance high)
- Market Efficiency: 7/10 (major conferences efficient, mid-majors not)
- Data Quality: 6/10 (good for D1, poor for smaller schools)
- Technical Difficulty: 5/10 (ELO/ratings models work)
- ROI Potential: 7/10 (mid-major conferences exploitable)

**Recommendation:** Good opportunity for:
- Mid-major basketball conferences
- College football totals
- Conference tournaments

**Lessons from NHL:** Similar to lower-tier soccer - less efficient markets compensate for higher variance.

---

### 6. Tennis

**Overview:** Individual sport, year-round ATP/WTA tours.

**Pros:**
- Individual performance (no team dynamics)
- Abundant match data
- Surface types create specialization
- Many matches daily

**Cons:**
- Very efficient markets (sharp bettors)
- Injuries common and match-ending
- Motivation issues (tanking, scheduling)
- Weather delays impact

**Evaluation:**
- Predictability: 7/10 (individual skill shows through)
- Market Efficiency: 3/10 (very efficient, Pinnacle/Betfair sharp)
- Data Quality: 8/10 (good historical data)
- Technical Difficulty: 6/10 (surface + form + head-to-head)
- ROI Potential: 4/10 (edges small)

**Recommendation:** Not recommended unless:
- Focus on live betting (odds swing wildly)
- Lower-tier challenger events
- Women's tennis (slightly less efficient)

---

### 7. MMA/Boxing (Combat Sports)

**Overview:** One-off events, high variance, subjective judging.

**Pros:**
- Public often bets emotionally (name value)
- Small fighter pools (deep analysis feasible)
- Matchup-specific (styles make fights)

**Cons:**
- Very small sample sizes per fighter
- Injuries/weight cuts unpredictable
- Judging controversial
- Limited historical data

**Evaluation:**
- Predictability: 3/10 (knockouts random)
- Market Efficiency: 6/10 (moderate - casuals bet favorites)
- Data Quality: 4/10 (limited historical data)
- Technical Difficulty: 8/10 (domain expertise critical)
- ROI Potential: 6/10 (edges exist for experts)

**Recommendation:** Only if you have deep MMA/boxing knowledge. Too specialized for general ML approach.

---

## Esports Opportunities

### 8. League of Legends (LoL)

**Overview:** Team-based MOBA, professional leagues globally.

**Pros:**
- Young markets (less efficient than traditional sports)
- Abundant data (every action tracked digitally)
- Patch updates create temporary inefficiencies
- International tournaments high variance

**Cons:**
- Meta shifts rapidly (patches change viability)
- Player rosters change frequently
- Relatively new (limited historical data)
- Markets becoming more efficient

**Evaluation:**
- Predictability: 6/10 (team skill matters but meta shifts)
- Market Efficiency: 7/10 (improving, but still beatable)
- Data Quality: 9/10 (digital = perfect tracking)
- Technical Difficulty: 8/10 (need to understand meta)
- ROI Potential: 7/10 (inefficiencies remain)

**Recommendation:** Good opportunity if:
- You understand LoL meta deeply
- Can model champion picks/bans
- Follow roster changes closely
- Focus on lower-tier regional leagues

**Lessons from NHL:** Esports markets are younger and less efficient. Data quality is excellent (digital tracking). Potential for better ROI than traditional sports.

---

### 9. CS:GO / Valorant (FPS)

**Overview:** Team-based tactical shooters, map-specific strategies.

**Pros:**
- Map-specific data (analyze map by map)
- Round-by-round betting available
- Lower-tier tournaments less efficient

**Cons:**
- Similar efficiency issues as LoL
- Player form highly variable
- Roster changes common

**Evaluation:**
- Predictability: 6/10
- Market Efficiency: 7/10
- Data Quality: 8/10
- Technical Difficulty: 7/10
- ROI Potential: 7/10

**Recommendation:** Similar to LoL - good if you have domain expertise.

---

### 10. Dota 2

**Overview:** Similar to LoL but different meta.

**Evaluation:**
- Predictability: 6/10
- Market Efficiency: 7/10
- Data Quality: 9/10
- Technical Difficulty: 8/10
- ROI Potential: 7/10

**Recommendation:** Choose ONE esport to specialize in. Don't spread thin across multiple games.

---

## Financial Markets

### 11. Stock Market Prediction

**Overview:** Predict stock price movements.

**Pros:**
- Massive data availability
- High-frequency opportunities
- Algorithmic trading infrastructure exists

**Cons:**
- EXTREMELY efficient markets
- Requires significant capital
- Transaction costs high
- Regulatory complexity
- Competition from hedge funds with unlimited resources

**Evaluation:**
- Predictability: 3/10 (efficient market hypothesis largely true)
- Market Efficiency: 1/10 (most efficient market in existence)
- Data Quality: 10/10
- Technical Difficulty: 10/10 (PhD-level quant work)
- ROI Potential: 2/10 (for retail traders)

**Recommendation:** NOT recommended unless:
- You have PhD in quantitative finance
- Access to proprietary data/infrastructure
- Significant capital ($100K+ minimum)

---

### 12. Cryptocurrency Prediction

**Overview:** Predict crypto price movements.

**Pros:**
- Less efficient than stock markets
- 24/7 trading (more opportunities)
- Lower regulatory barriers

**Cons:**
- Extremely high volatility
- Manipulation common
- No fundamental valuation model
- Technical analysis largely discredited

**Evaluation:**
- Predictability: 2/10 (mostly random walk + manipulation)
- Market Efficiency: 4/10 (inefficient but exploited by bots)
- Data Quality: 6/10 (some data, much noise)
- Technical Difficulty: 9/10
- ROI Potential: 3/10 (high risk, low edge)

**Recommendation:** NOT recommended. High risk, little edge.

---

## Non-Sports Predictions

### 13. Political Election Forecasting

**Overview:** Predict election outcomes.

**Pros:**
- Markets (PredictIt, Polymarket) exist
- Polls provide data
- Media coverage abundant

**Cons:**
- Infrequent events (small sample size)
- Polls increasingly unreliable
- High stakes → emotional betting
- Legal restrictions in many jurisdictions

**Evaluation:**
- Predictability: 5/10 (polls sometimes wrong)
- Market Efficiency: 6/10 (biased by partisan bettors)
- Data Quality: 5/10 (polls noisy)
- Technical Difficulty: 7/10 (poll aggregation + modeling)
- ROI Potential: 6/10 (opportunities exist but rare)

**Recommendation:** Occasional opportunity during election years. Not sustainable year-round.

---

### 14. Weather Betting

**Overview:** Bet on temperature, precipitation, etc.

**Pros:**
- Weather models exist (NOAA, etc.)
- Data abundant
- Some markets offer weather derivatives

**Cons:**
- Very limited betting markets
- Weather is chaotic (hard to beat models)
- Low liquidity

**Evaluation:**
- Predictability: 4/10
- Market Efficiency: 5/10
- Data Quality: 9/10
- Technical Difficulty: 9/10 (meteorology expertise)
- ROI Potential: 3/10

**Recommendation:** Not viable for retail bettors.

---

### 15. Entertainment (Oscars, Reality TV, etc.)

**Overview:** Predict award winners, reality show outcomes.

**Pros:**
- Markets exist (Oscars betting popular)
- Inside information sometimes leaks
- Casual bettors create inefficiency

**Cons:**
- Very infrequent events
- Small betting limits
- Results sometimes leaked/rigged
- Not sustainable income

**Evaluation:**
- Predictability: 6/10
- Market Efficiency: 7/10 (improving)
- Data Quality: 5/10
- Technical Difficulty: 6/10
- ROI Potential: 5/10 (fun but not serious)

**Recommendation:** Recreational only. Not a viable system.

---

## Alternative NHL Markets

### 16. NHL Totals (Over/Under)

**Overview:** Bet on total goals scored in game.

**Pros:**
- Different factors than moneyline (goalies, pace)
- Potentially less efficient than game outcome
- Weather matters (outdoor games)

**Cons:**
- Still NHL (same parity issues)
- Bookmakers sharp on totals too

**Evaluation:**
- Predictability: 5/10
- Market Efficiency: 5/10 (moderate)
- Data Quality: 10/10 (same as moneyline model)
- Technical Difficulty: 6/10 (need new features)
- ROI Potential: 6/10

**Recommendation:** Worth exploring. Could use existing ELO + goalie data but model total goals instead of winner.

**Implementation:**
- Predict goals for/against using team offensive/defensive ratings
- Model as Poisson distribution
- Calibrate to over/under lines

---

### 17. NHL Puck Lines (Spread)

**Overview:** Bet on margin of victory (typically ±1.5 goals).

**Pros:**
- Different odds than moneyline
- Favorites get better value
- Empty net goals matter (late-game variance)

**Cons:**
- 1-goal games very common in NHL (tough to predict margin)
- Similar efficiency to moneyline

**Evaluation:**
- Predictability: 4/10 (margins random)
- Market Efficiency: 5/10
- Data Quality: 10/10
- Technical Difficulty: 6/10
- ROI Potential: 5/10

**Recommendation:** Marginal opportunity. Might combine with moneyline model.

---

### 18. NHL Player Props

**Overview:** Bet on individual player performance (goals, assists, points).

**Pros:**
- Many props offered per game
- Less efficient than game outcomes
- Can exploit matchups

**Cons:**
- Betting limits lower
- High variance (one player in one game)
- Bookmakers adjust quickly to sharp action

**Evaluation:**
- Predictability: 5/10
- Market Efficiency: 6/10 (less efficient than moneyline)
- Data Quality: 8/10 (player stats available)
- Technical Difficulty: 7/10 (player-level modeling)
- ROI Potential: 6/10

**Recommendation:** Good opportunity if:
- Build player-level shot/goal models
- Analyze ice time, linemates, matchups
- Diversify across many small bets

---

### 19. NHL Live Betting (In-Game)

**Overview:** Bet on games as they happen.

**Pros:**
- Odds swing rapidly (market inefficiency)
- Can observe momentum, injuries, goalie performance
- More betting opportunities per game

**Cons:**
- Requires real-time monitoring (can't automate easily)
- Emotional betting increases (tilt risk)
- Lines move fast (execution risk)

**Evaluation:**
- Predictability: 6/10 (more information available)
- Market Efficiency: 6/10 (moderate)
- Data Quality: 7/10 (real-time stats)
- Technical Difficulty: 8/10 (need real-time infrastructure)
- ROI Potential: 7/10 (good for manual betting)

**Recommendation:** Good opportunity but requires:
- Real-time data feeds
- Quick decision-making
- Emotional discipline

---

## Top 5 Recommendations

Based on evaluation scores and lessons learned from NHL project:

### 1. Lower-Tier Soccer Leagues (ROI: 7/10)

**Why:** Less efficient markets, good data available, many games.

**How to Start:**
- Pick one league (e.g., English Championship, Spanish Segunda)
- Build ELO system (same as NHL)
- Add xG data if available
- Test with paper trading first

**Time Investment:** 3-4 months to build and validate

**Expected ROI:** 3-5% if disciplined

---

### 2. NCAA Mid-Major Basketball (ROI: 7/10)

**Why:** Market inefficiencies in smaller conferences.

**How to Start:**
- Use KenPom or similar ratings as baseline
- Build conference-specific ELO
- Focus on conference tournaments
- Avoid major conferences (too efficient)

**Time Investment:** 2-3 months

**Expected ROI:** 4-6% on mid-majors

---

### 3. Esports (LoL or CS:GO) (ROI: 7/10)

**Why:** Young markets, excellent data, inefficiencies remain.

**How to Start:**
- Choose ONE game (don't spread thin)
- Learn the meta deeply
- Build team ELO + map-specific ratings
- Focus on regional leagues (not international)

**Time Investment:** 4-6 months (need domain expertise)

**Expected ROI:** 5-8% if you understand the game

---

### 4. NHL Totals + Player Props (ROI: 6/10)

**Why:** Leverage existing NHL infrastructure, different market.

**How to Start:**
- Use existing game_features data
- Model total goals (Poisson distribution)
- Build player-level shot models
- Combine with existing ELO ratings

**Time Investment:** 1-2 months (leverage existing work)

**Expected ROI:** 3-4% (similar to moneyline)

---

### 5. MLB Totals (Over/Under) (ROI: 6/10)

**Why:** Weather + ballpark + pitcher = modelable factors.

**How to Start:**
- Scrape weather data (wind speed/direction critical)
- Build pitcher effectiveness model (FIP, xFIP)
- Factor in ballpark dimensions
- Model run production per inning

**Time Investment:** 3-4 months

**Expected ROI:** 4-5% on totals

---

## What NOT to Pursue

Based on evaluation framework:

1. **Stock market** - Too efficient, need institutional resources
2. **Cryptocurrency** - Too random, too manipulated
3. **NFL/NBA moneylines** - Markets too efficient for retail bettors
4. **High-frequency trading** - Requires infrastructure you don't have
5. **Weather derivatives** - Too specialized, no market access
6. **MMA/Boxing** - Too small sample sizes, need deep expertise

---

## Decision Framework

**Before starting any new prediction model, ask:**

1. **Do I have an edge?**
   - What do I know that the market doesn't?
   - Can I access better data?
   - Is there a structural inefficiency?

2. **Can I validate cheaply?**
   - Can I paper trade first?
   - Is historical data available?
   - Can I test without risking capital?

3. **Is calibration achievable?**
   - Can I generate probabilities (not just picks)?
   - Is sample size sufficient?
   - Does the domain allow for proper validation?

4. **Is ROI worth effort?**
   - Expected annual return > 5%?
   - Can I scale to meaningful bankroll?
   - Is betting market liquid enough?

5. **Do I have domain knowledge?**
   - Do I understand the sport/game/market?
   - Can I interpret model outputs?
   - Will I stick with it long-term?

**If you can't answer "yes" to 4/5 questions, skip the opportunity.**

---

## Lessons from NHL Applied to New Opportunities

### 1. Start Simple (ELO First)

Don't build complex multi-feature models immediately. Start with:
- Team/player strength ratings (ELO or similar)
- Simple logistic regression
- Platt scaling calibration

Validate this baseline before adding features.

### 2. Feature Engineering is Hard

Only add features if:
- Correlation with outcome >0.10
- Coefficient is significant and correct sign
- Calibration improves or stays constant
- Sample size doesn't drop >10%

**NHL showed:** Weak features (rest days, season GAA) made model worse.

### 3. Calibration > Accuracy

For betting, you MUST have well-calibrated probabilities. A model with 53% accuracy and 3% calibration beats 56% accuracy with 8% calibration.

**Metric priority:**
1. Calibration error (<5%)
2. Brier score (<0.250)
3. Accuracy (>53%)

### 4. Paper Trade First

Never risk real money until:
- 50+ paper bets placed
- Calibration validated on paper trades
- ROI positive over meaningful sample
- Understand variance and drawdowns

### 5. Accept Limitations

If market is efficient and data is public:
- Probabilities will compress toward 50%
- Edges will be small (2-4%)
- You won't predict blow-outs
- Volume and discipline matter more than sophistication

**Don't fight it. Work with it.**

---

## Recommended Path Forward

**Option A: Expand NHL System (Low Risk)**
- Build NHL totals model
- Add player props
- Try live betting
- Leverage existing infrastructure

**Time:** 1-2 months
**Risk:** Low (know the domain)
**Expected ROI:** 3-5%

**Option B: New Sport - Lower-Tier Soccer (Medium Risk)**
- Pick one league (Championship, Ligue 2, etc.)
- Build ELO system
- Add xG data
- Paper trade full season

**Time:** 3-4 months
**Risk:** Medium (new domain)
**Expected ROI:** 4-6%

**Option C: Esports - League of Legends (High Risk, High Reward)**
- Learn LoL meta deeply
- Build team + champion ELO
- Focus on regional leagues
- Paper trade extensively

**Time:** 4-6 months
**Risk:** High (need game knowledge)
**Expected ROI:** 5-8% if successful

**Option D: MLB Totals (Medium Risk)**
- Build weather + pitcher + ballpark model
- Focus on over/under
- Paper trade half season

**Time:** 3-4 months
**Risk:** Medium (new sport)
**Expected ROI:** 4-5%

---

## Final Recommendation

**If you want to maximize learning and potential ROI:**

**Pursue Option B (Lower-Tier Soccer) OR Option C (Esports)**

**Why:**
- Genuine market inefficiencies (unlike NHL)
- Good data quality
- Learnable domain (don't need to be expert)
- Higher expected ROI (5-8% vs 3-4%)
- Diversification from hockey

**However, if you want to minimize risk:**

**Pursue Option A (Expand NHL)**

**Why:**
- Leverage existing code and knowledge
- Proven domain understanding
- Lower time investment
- Incremental improvement to existing system

**The choice depends on:** Risk tolerance, time availability, and whether you want to branch out vs deepen NHL expertise.

---

## Conclusion

**Key Insights:**

1. **Not all prediction problems are equal** - NHL taught us that parity and efficiency limit edges
2. **Inefficient markets exist** - Esports, lower-tier sports, niche props
3. **Data quality matters** - Digital tracking (esports) > manual recording (combat sports)
4. **Start simple, add complexity only if validated** - ELO first, features second
5. **Calibration is critical** - For betting, accurate probabilities matter more than directional accuracy

**The NHL project was successful** (54.98% accuracy, 4.03% calibration), but taught us that:
- Public data has limits
- Market efficiency is real
- ELO captures most available signal
- Adding weak features hurts more than helps

**Apply these lessons to new domains** - find where markets are inefficient, data is good, and signal exists. Build simple models first, validate rigorously, and scale conservatively.

**Good luck!**

---

**Created:** June 25, 2026
**Based on:** NHL betting model Phase 1 + Phase 2 investigation
**Status:** Analysis complete - Ready for decision

# Docker Setup Guide - NHL Betting Model

## Current Status

### ✅ Completed (Phase 1 & 2)
- [x] Fixed Flyway configuration to connect to local Postgres container
- [x] Created `pipelines/Dockerfile` for Python environment
- [x] Added `pipeline-runner` service to `docker-compose.yml`
- [x] Configured volume mounting for live code editing
- [x] Set up proper environment variable handling
- [x] Tested pipeline-runner container build (Python 3.11.15)
- [x] Verified pipeline scripts run correctly in container
- [x] Created `backend-api/Dockerfile` for Spring Boot
- [x] Added `backend-api` service to docker-compose.yml
- [x] Tested full stack (Postgres → Flyway → Backend API → Pipelines)

### 🔲 To-Do (Phase 3)
- [ ] Set up scheduled pipeline runs (cloud deployment)
- [ ] Configure CI/CD pipeline
- [ ] Set up monitoring and alerting

---

## Architecture Overview

### Current Docker Services

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐   ┌───────────────┐  │
│  │   Postgres   │◄───│    Flyway    │   │   pgAdmin     │  │
│  │  (Port 5432) │    │  (Migrations)│   │  (Port 5050)  │  │
│  └──────┬───────┘    └──────────────┘   └───────────────┘  │
│         │                                                    │
│         │ JDBC/psycopg connections                           │
│         │                                                    │
│  ┌──────▼──────────────────────────────┐                    │
│  │   Backend API (Spring Boot) ✅      │                    │
│  │  • REST endpoints                   │                    │
│  │  • Port 8080                        │                    │
│  │  • Java 21 / Multi-stage build      │                    │
│  └─────────────────────────────────────┘                    │
│                                                              │
│  ┌─────────────────────────────────────┐                    │
│  │   Pipeline Runner (Python) ✅       │                    │
│  │  • ETL scripts                      │                    │
│  │  • Betting scripts                  │                    │
│  │  • Analysis scripts                 │                    │
│  │  • Python 3.11 / Volume mounted     │                    │
│  └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Benefits of Each Component

### 1. Pipeline Runner (Python) ✅ DONE
**Benefits:**
- No manual Python virtual environment setup
- Consistent Python 3.11 across all machines
- Dependencies frozen in Docker image
- Live code editing with volume mounts
- Easy to schedule in cloud (AWS ECS, Google Cloud Run)
- Database connection handled via environment variables

**Use Cases:**
- Daily ETL jobs (ingest goalie stats, game features)
- Bet selection automation
- Model training and analysis
- Data backfills

---

### 2. Backend API (Spring Boot) ✅ DONE
**Benefits:**
- Deploy to any cloud provider (AWS, Google Cloud, Azure)
- Auto-scaling based on traffic
- Zero-downtime deployments
- HTTPS and SSL handled by cloud
- Health checks and automatic restarts
- Consistent Java 21 environment

**Use Cases:**
- REST API for frontend/mobile apps
- Real-time odds display
- Bet tracking endpoints
- Historical analysis queries

---

## Essential Docker Commands

### Navigation
```bash
# Always run docker-compose commands from this directory:
cd "C:\Users\Nathan\Downloads\[My Projects]\nhl-betting-model\infra\docker"
```

---

### Building & Managing Containers

```bash
# Build all services
docker-compose build

# Build only pipeline-runner (after changing Dockerfile)
docker-compose build pipeline-runner

# Build from scratch (ignore cache)
docker-compose build --no-cache pipeline-runner

# Start all services in background
docker-compose up -d

# Start specific service
docker-compose up -d postgres

# Stop all services
docker-compose down

# Stop and remove volumes (DELETES DATABASE!)
docker-compose down -v

# View running containers
docker-compose ps

# View logs
docker-compose logs -f pipeline-runner
docker-compose logs -f postgres
```

---

### Running Python Scripts via Container

#### One-off Script Execution
```bash
# Run a single pipeline script
docker-compose run --rm pipeline-runner python etl/ingest_goalie_stats.py

# Run with arguments
docker-compose run --rm pipeline-runner python betting/select_bets.py --date 2026-05-02

# Run analysis script
docker-compose run --rm pipeline-runner python analysis/train_baseline_model.py

# Interactive Python shell in container
docker-compose run --rm pipeline-runner python

# Bash shell in container (for debugging)
docker-compose run --rm pipeline-runner bash
```

#### Common Pipeline Commands

```bash
# ETL Pipelines
docker-compose run --rm pipeline-runner python etl/ingest_goalie_stats.py
docker-compose run --rm pipeline-runner python etl/backfill_goalie_data.py
docker-compose run --rm pipeline-runner python etl/calculate_goalie_stats.py
docker-compose run --rm pipeline-runner python etl/create_missing_game_features.py
docker-compose run --rm pipeline-runner python etl/update_game_features_elos.py
docker-compose run --rm pipeline-runner python etl/update_game_features_goalies.py

# Betting Pipelines
docker-compose run --rm pipeline-runner python betting/select_bets.py
docker-compose run --rm pipeline-runner python betting/select_paper_bets.py
docker-compose run --rm pipeline-runner python betting/preview_edges.py

# Pricing Pipelines
docker-compose run --rm pipeline-runner python pricing/compute_edges.py
docker-compose run --rm pipeline-runner python pricing/compute_game_pricing_elos.py

# Analysis Scripts
docker-compose run --rm pipeline-runner python analysis/train_baseline_model.py
docker-compose run --rm pipeline-runner python analysis/train_platt_scaling.py
docker-compose run --rm pipeline-runner python analysis/train_with_goalies.py
docker-compose run --rm pipeline-runner python analysis/replay_elos.py
```

#### Ad-hoc Scripts (from project root)
```bash
# These are in the project root, not pipelines/
docker-compose run --rm -v ../../:/scripts pipeline-runner python /scripts/analyze_bet.py
docker-compose run --rm -v ../../:/scripts pipeline-runner python /scripts/check_edges.py
docker-compose run --rm -v ../../:/scripts pipeline-runner python /scripts/check_elos.py
docker-compose run --rm -v ../../:/scripts pipeline-runner python /scripts/show_bet_status.py
```

---

### Database Management

```bash
# Connect to Postgres via psql
docker-compose exec postgres psql -U postgres -d postgres

# Run a SQL query
docker-compose exec postgres psql -U postgres -d postgres -c "SELECT COUNT(*) FROM games;"

# Dump database to file
docker-compose exec postgres pg_dump -U postgres postgres > backup.sql

# Restore from backup
cat backup.sql | docker-compose exec -T postgres psql -U postgres postgres

# View Flyway migration status
docker-compose run --rm flyway info

# Run pending migrations
docker-compose run --rm flyway migrate
```

---

### Debugging & Inspection

```bash
# View container logs (live tail)
docker-compose logs -f pipeline-runner

# View last 100 lines of logs
docker-compose logs --tail=100 pipeline-runner

# Check container status
docker-compose ps

# See resource usage
docker stats

# Inspect container details
docker inspect nhl_pipeline_runner

# List all Docker images
docker images

# Remove unused images/containers (cleanup)
docker system prune -a
```

---

## Hybrid Development Workflow (Recommended)

**For day-to-day development, use a hybrid approach**: Local development for speed and flexibility, Docker for production testing and deployment.

### When to Use Docker vs Local

| Task | Use Local | Use Docker |
|------|-----------|------------|
| **Daily coding/debugging** | ✅ Fast, IDE support | ❌ Slower iteration |
| **Running quick scripts** | ✅ No overhead | ❌ Container startup time |
| **Testing for production** | ❌ Environment differs | ✅ Matches production |
| **Sharing with team** | ❌ "Works on my machine" | ✅ Consistent environment |
| **Cloud deployment** | ❌ Can't deploy local env | ✅ Same image everywhere |
| **Long-running jobs** | ❌ Ties up local machine | ✅ Can run on cloud 24/7 |

### Daily Routine

#### Morning Setup (One Command)
```bash
# Start infrastructure services
cd infra/docker
docker-compose up -d postgres pgadmin

# Verify they're running
docker-compose ps
```

#### During Development (Local Python/Java)
```bash
# Work normally - no Docker needed!
cd pipelines
python etl/ingest_goalie_stats.py
python betting/select_bets.py
python analysis/train_baseline_model.py

# Root-level helper scripts
cd ..
python check_edges.py
python show_bet_status.py

# Java development (if needed)
cd backend-api
./gradlew bootRun
```

#### Pre-Deployment Testing (Docker Containers)
```bash
# "Does this work in a production-like environment?"
cd infra/docker
docker-compose run --rm pipeline-runner python betting/select_bets.py

# Or start the API
docker-compose up -d backend-api
curl http://localhost:8080/api/health
```

#### Evening Cleanup (Optional)
```bash
# Stop services to free resources
cd infra/docker
docker-compose down

# OR leave postgres running (it's lightweight)
# Just stop the API if running
docker-compose stop backend-api
```

---

## Command Aliases (Save Time!)

Docker commands can be verbose. Set up aliases to save typing.

### For Git Bash (Windows)

Add these to `~/.bashrc`:

```bash
# Navigate to docker directory
alias cdd='cd "/c/Users/Nathan/Downloads/[My Projects]/nhl-betting-model/infra/docker"'

# Docker Compose shortcuts
alias dcu='docker-compose up -d'
alias dcd='docker-compose down'
alias dcp='docker-compose ps'
alias dcl='docker-compose logs -f'

# Pipeline runner shortcuts
alias dpy='docker-compose run --rm pipeline-runner python'
alias dpysh='docker-compose run --rm pipeline-runner bash'

# Database shortcuts
alias dpsql='docker-compose exec postgres psql -U postgres -d postgres'
alias dbstart='docker-compose up -d postgres pgadmin'
```

**Reload your terminal:**
```bash
source ~/.bashrc
```

### For Linux/Mac (bash/zsh)

Add these to `~/.bashrc` or `~/.zshrc`:

```bash
# Navigate to docker directory
alias cdd='cd "$HOME/projects/nhl-betting-model/infra/docker"'

# Docker Compose shortcuts
alias dcu='docker-compose up -d'
alias dcd='docker-compose down'
alias dcp='docker-compose ps'
alias dcl='docker-compose logs -f'

# Pipeline runner shortcuts
alias dpy='docker-compose run --rm pipeline-runner python'
alias dpysh='docker-compose run --rm pipeline-runner bash'

# Database shortcuts
alias dpsql='docker-compose exec postgres psql -U postgres -d postgres'
alias dbstart='docker-compose up -d postgres pgadmin'
```

**Reload your terminal:**
```bash
source ~/.bashrc  # or source ~/.zshrc
```

### Using the Aliases

#### Example 1: Start database quickly
```bash
# Without alias
cd "C:\Users\Nathan\Downloads\[My Projects]\nhl-betting-model\infra\docker"
docker-compose up -d postgres pgadmin

# With alias
dbstart
```

#### Example 2: Run a pipeline script
```bash
# Without alias
cd "C:\Users\Nathan\Downloads\[My Projects]\nhl-betting-model\infra\docker"
docker-compose run --rm pipeline-runner python etl/ingest_goalie_stats.py

# With alias
cdd && dpy etl/ingest_goalie_stats.py
```

#### Example 3: Check database
```bash
# Without alias
cd "C:\Users\Nathan\Downloads\[My Projects]\nhl-betting-model\infra\docker"
docker-compose exec postgres psql -U postgres -d postgres -c "SELECT COUNT(*) FROM bet_log;"

# With alias
dpsql -c "SELECT COUNT(*) FROM bet_log;"
```

#### Example 4: View container logs
```bash
# Without alias
docker-compose logs -f backend-api

# With alias
cdd && dcl backend-api
```

#### Example 5: Debug in container
```bash
# Without alias
docker-compose run --rm pipeline-runner bash

# With alias
dpysh
```

### Pro Tip: Project-Specific Aliases

Create aliases for your common workflows:

```bash
# Add to ~/.bashrc

# Daily workflow aliases
alias nhl-start='cdd && docker-compose up -d postgres pgadmin'
alias nhl-stop='cdd && docker-compose down'
alias nhl-ingest='cdd && dpy etl/ingest_goalie_stats.py'
alias nhl-bets='cdd && dpy betting/select_bets.py'
alias nhl-edges='cdd && dpy pricing/compute_edges.py'
alias nhl-status='cdd && docker-compose ps'
```

**Usage:**
```bash
# Start your day
nhl-start

# Run daily workflow (from anywhere!)
nhl-ingest
nhl-edges
nhl-bets

# Check what's running
nhl-status

# End your day
nhl-stop
```

---

## Switching Between Local and Docker Postgres

Your `pipelines/.env` file controls which database your scripts connect to.

### Current Setup: Remote Supabase
```bash
# pipelines/.env (current)
DATABASE_URL="host=aws-1-us-east-2.pooler.supabase.com port=6543 ..."
```

**Result**: Both local Python AND Docker container connect to Supabase cloud.

### To Use Local Docker Postgres
```bash
# pipelines/.env (for local development)
DATABASE_URL=postgresql://postgres:postgres@localhost:55432/postgres
```

**Result**: Local Python connects to Docker postgres on localhost:55432.

**Note**: The Docker container ALWAYS uses the hostname `postgres:5432` internally (Docker networking).

### Best Practice: Use Environment-Specific Files

```bash
# Keep both configurations
pipelines/.env.local         # Local Docker postgres
pipelines/.env.production    # Remote Supabase

# Copy the one you want to use
cp pipelines/.env.local pipelines/.env
```

---

## What Needs to Be Done

### Phase 1: Test Pipeline Runner ✅ COMPLETED

**Status:** Pipeline Runner successfully tested and verified.

**What Was Tested:**

1. **Container Build:**
   ```bash
   docker-compose build pipeline-runner
   # ✅ Built successfully with Python 3.11.15
   ```

2. **Python Version:**
   ```bash
   docker-compose run --rm pipeline-runner python --version
   # ✅ Output: Python 3.11.15
   ```

3. **Database Connection:**
   ```bash
   # Tested connection to Supabase (remote)
   # ✅ Successfully connected and queried 4,215 game results
   ```

**Issues Resolved:**
- ✅ Fixed Dockerfile: Moved `FROM` before `LABEL`
- ✅ Fixed requirements.txt: Changed `beautifulsoup4>4.14.3` to `beautifulsoup4>=4.14.3`
- ✅ Verified volume mounts work correctly

**Current Configuration:**
- Database: Connects to **Supabase (remote)** via `pipelines/.env`
- Can switch to local Docker postgres by updating `DATABASE_URL`

---

### Phase 2: Containerize Spring Boot Backend ✅ COMPLETED

**Status:** Backend API successfully containerized with multi-stage Docker build.

**What Was Done:**

1. **Created `backend-api/Dockerfile`** with multi-stage build:
   - Build stage: Gradle 8 + JDK 21 (compiles code)
   - Runtime stage: JRE 21 only (runs JAR)
   - Result: ~300MB runtime image vs 1GB+ if we kept build tools

2. **Added `backend-api` service to `docker-compose.yml`**:
   - Depends on healthy postgres container
   - Connects to local Docker postgres
   - Exposes port 8080
   - Auto-restart capability

3. **Fixed Gradle compatibility issue**:
   - Removed duplicate `prepareKotlinBuildScriptModel` task
   - Gradle 8.14 includes this task by default

**Verification:**
```bash
# Build successful
docker-compose build backend-api

# Container runs
docker-compose up -d backend-api

# Health check (once you add endpoints)
curl http://localhost:8080/actuator/health
```

**Benefits Achieved:**
- ✅ Consistent Java 21 environment
- ✅ Easy deployment to cloud platforms
- ✅ Multi-stage build keeps image small (~70% size reduction)
- ✅ Ready for health checks and auto-restart

---

### Phase 3: Cloud Deployment & Scheduling 🔲 FUTURE
**Goal:** Run pipelines on a schedule without local machine

**Options:**

#### Option A: AWS ECS (Elastic Container Service)
```bash
# Push image to ECR
aws ecr create-repository --repository-name nhl-pipeline-runner
docker tag nhl-pipeline-runner:latest <account>.dkr.ecr.us-east-1.amazonaws.com/nhl-pipeline-runner
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/nhl-pipeline-runner

# Create scheduled task
aws events put-rule --schedule-expression "cron(0 10 * * ? *)" --name daily-goalie-ingest
aws events put-targets --rule daily-goalie-ingest --targets "Id=1,Arn=<ecs-cluster-arn>,EcsParameters={TaskDefinitionArn=<task-def>}"
```

#### Option B: Google Cloud Run Jobs
```bash
# Deploy container
gcloud run jobs create goalie-ingest \
  --image gcr.io/<project>/pipeline-runner \
  --command "python,etl/ingest_goalie_stats.py" \
  --schedule "0 10 * * *"
```

**Benefits:**
- Runs even when your PC is off
- Automatic retries on failure
- Logging and monitoring built-in
- Pay only for execution time (serverless)
- Easy to change schedules

---

## Environment Variables Guide

### For Pipeline Runner (`pipelines/.env`)
```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/postgres

# TheOdds API
THEODDS_API_KEY=your_key_here
THEODDS_API_SPORT=icehockey_nhl
THEODDS_REGION=us
THEODDS_API_MARKETS=h2h,spreads,totals

# Betting Config
BANKROLL=1000
POINT_SCALE=100
BOOKS=draftkings,fanduel,betmgm
```

### For Infrastructure (`shared/config/.env`)
```bash
# Already configured
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_PORT=55432
```

---

## Troubleshooting

### Container won't build
```bash
# Clear Docker cache
docker-compose build --no-cache pipeline-runner

# Check for syntax errors in Dockerfile
cat pipelines/Dockerfile
```

### Container won't start
```bash
# Check logs
docker-compose logs pipeline-runner

# Check if postgres is healthy
docker-compose ps
```

### Can't connect to database
```bash
# Verify postgres is running
docker-compose ps postgres

# Test connection from host
docker-compose exec postgres psql -U postgres -d postgres

# Check environment variables in container
docker-compose run --rm pipeline-runner env | grep DATABASE
```

### Python import errors
```bash
# Verify requirements are installed
docker-compose run --rm pipeline-runner pip list

# Rebuild without cache
docker-compose build --no-cache pipeline-runner
```

### File not found errors
```bash
# Verify volume mount
docker-compose run --rm pipeline-runner ls -la

# Check docker-compose.yml volumes section
cat docker-compose.yml | grep -A 2 volumes
```

---

## Quick Reference

### Hybrid Workflow (Recommended)

#### Daily Development
```bash
# Morning: Start database
cd infra/docker
docker-compose up -d postgres pgadmin
# OR with alias: dbstart

# Work locally throughout the day
cd ../../pipelines
python etl/ingest_goalie_stats.py
python betting/select_bets.py
python pricing/compute_edges.py

# Evening: Stop (optional - postgres is lightweight)
cd ../infra/docker
docker-compose down
# OR with alias: nhl-stop
```

#### Production Testing (Before Deployment)
```bash
# Test in container (matches production)
cd infra/docker
docker-compose run --rm pipeline-runner python betting/select_bets.py
# OR with alias: cdd && dpy betting/select_bets.py

# Start API for integration testing
docker-compose up -d backend-api
curl http://localhost:8080/api/health
```

### Full Docker Workflow

#### Start Everything
```bash
cd infra/docker
docker-compose up -d
# OR with alias: dcu
```

#### Run Daily Workflow (All in Docker)
```bash
cd infra/docker

# 1. Ingest latest data
docker-compose run --rm pipeline-runner python etl/ingest_goalie_stats.py

# 2. Update features
docker-compose run --rm pipeline-runner python etl/update_game_features_goalies.py

# 3. Compute pricing
docker-compose run --rm pipeline-runner python pricing/compute_edges.py

# 4. Select bets
docker-compose run --rm pipeline-runner python betting/select_bets.py

# With aliases:
# dpy etl/ingest_goalie_stats.py
# dpy etl/update_game_features_goalies.py
# dpy pricing/compute_edges.py
# dpy betting/select_bets.py
```

#### Stop Everything
```bash
cd infra/docker
docker-compose down
# OR with alias: dcd
```

#### Clean Up (Fresh Start)
```bash
cd infra/docker
docker-compose down -v  # WARNING: Deletes database!
docker-compose up -d
```

### Database Quick Access
```bash
# Connect to postgres
docker-compose exec postgres psql -U postgres -d postgres
# OR with alias: dpsql

# Run quick query
docker-compose exec postgres psql -U postgres -d postgres -c "SELECT COUNT(*) FROM bet_log;"
# OR with alias: dpsql -c "SELECT COUNT(*) FROM bet_log;"

# View pgAdmin
# Open browser: http://localhost:5050
# Login: admin@admin.com / admin (from shared/config/.env)
```

### Container Management
```bash
# Check what's running
docker-compose ps
# OR with alias: dcp

# View logs
docker-compose logs -f backend-api
docker-compose logs -f pipeline-runner
# OR with alias: dcl backend-api

# Restart a service
docker-compose restart backend-api

# Rebuild after code changes
docker-compose build backend-api
docker-compose up -d backend-api
```

---

## Next Session Checklist

### For Hybrid Development (Recommended)

When you return to work:

1. [ ] Verify Docker Desktop is running
2. [ ] Start database: `cd infra/docker && docker-compose up -d postgres pgadmin`
3. [ ] Work locally: `cd pipelines && python your_script.py`
4. [ ] Test in container before deploying: `docker-compose run --rm pipeline-runner python your_script.py`

### For Full Docker Development

When you return to work:

1. [ ] Verify Docker Desktop is running
2. [ ] Navigate to `infra/docker` directory
3. [ ] Start services: `docker-compose up -d`
4. [ ] Check status: `docker-compose ps`
5. [ ] Run pipelines via Docker: `docker-compose run --rm pipeline-runner python script.py`
6. [ ] View logs if needed: `docker-compose logs -f service-name`

---

## Learning Resources

- **Docker Compose CLI:** `docker-compose --help`
- **Dockerfile Reference:** https://docs.docker.com/engine/reference/builder/
- **Docker Volumes:** https://docs.docker.com/storage/volumes/
- **Multi-stage Builds:** https://docs.docker.com/build/building/multi-stage/

---

*Last Updated: 2026-05-18*
*Status: Full Docker stack complete (Postgres, Flyway, Pipeline Runner, Backend API). Hybrid development workflow recommended.*

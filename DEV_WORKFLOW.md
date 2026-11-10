# Development Workflow - Start to Code

This guide shows the exact commands to run from opening a terminal to actively developing.

---

## Option 1: Hybrid Workflow (Recommended - Fast Development)

### Morning Setup (5 seconds)

```bash
# 1. Open Git Bash terminal in your IDE
# (Terminal should auto-load ~/.bashrc with aliases)

# 2. Start database infrastructure
nhl-start
# Output: Starting nhl_postgres... done
#         Starting nhl_pgadmin... done

# 3. Verify services are running
nhl-status
# Output: Should show postgres and pgadmin as "Up"
```

### Navigate and Code (Local Python)

```bash
# 4. Navigate to pipelines directory
cd ~/Downloads/[My Projects]/nhl-betting-model/pipelines

# 5. Check your environment
python --version
# Output: Python 3.11.x (your local Python)

# 6. Run scripts locally (fast iteration!)
python etl/ingest_goalie_stats.py
python betting/select_bets.py
python pricing/compute_edges.py

# 7. Check results in database
cd ../infra/docker
dpsql -c "SELECT COUNT(*) FROM bet_log;"
```

### Make Changes to Code

```bash
# 8. Open your editor (if not already open)
cd ~/Downloads/[My Projects]/nhl-betting-model
code .   # VSCode
# OR
idea .   # IntelliJ
# OR just use your IDE's file explorer

# 9. Edit files in your IDE
# - Make changes to pipelines/betting/select_bets.py
# - Save the file

# 10. Test your changes immediately (local)
cd pipelines
python betting/select_bets.py

# 11. Test in Docker container (production-like)
cdd
dpy betting/select_bets.py
```

### Evening Cleanup (Optional)

```bash
# 12. Stop services (or leave postgres running - it's lightweight)
nhl-stop
# Output: Stopping nhl_pgadmin... done
#         Stopping nhl_postgres... done
```

---

## Option 2: Full Docker Workflow (Production Testing)

### Morning Setup

```bash
# 1. Open Git Bash terminal in your IDE

# 2. Navigate to docker directory
cdd

# 3. Start all services
dcu
# Output: Starting nhl_postgres... done
#         Starting nhl_pgadmin... done
#         Starting nhl_backend_api... done

# 4. Check status
dcp
```

### Run Pipelines via Docker

```bash
# 5. Run scripts in containers
dpy etl/ingest_goalie_stats.py
dpy betting/select_bets.py
dpy pricing/compute_edges.py

# 6. Check database
dpsql -c "SELECT COUNT(*) FROM bet_log;"

# 7. View API logs
dcl backend-api
```

### Make Changes and Test

```bash
# 8. Edit code in your IDE
# - Files are volume-mounted, so changes reflect immediately

# 9. Re-run in container to test
dpy betting/select_bets.py

# 10. If you changed backend-api code, rebuild
docker-compose build backend-api
docker-compose up -d backend-api
```

### Evening Cleanup

```bash
# 11. Stop everything
dcd
```

---

## Complete Manual Commands (No Aliases)

If you haven't set up aliases or want to see what's happening:

### Morning Setup

```bash
# 1. Navigate to project
cd "C:/Users/Nathan/Downloads/[My Projects]/nhl-betting-model"

# 2. Start Docker services
cd infra/docker
docker-compose up -d postgres pgadmin

# 3. Check status
docker-compose ps

# Expected output:
# NAME           STATUS              PORTS
# nhl_postgres   Up (healthy)        0.0.0.0:55432->5432/tcp
# nhl_pgadmin    Up                  127.0.0.1:5050->80/tcp
```

### Work Locally (Fastest)

```bash
# 4. Navigate to pipelines
cd ../../pipelines

# 5. Run scripts with local Python
python etl/ingest_goalie_stats.py
python betting/select_bets.py

# 6. Or use root-level helper scripts
cd ..
python check_edges.py
python show_bet_status.py
```

### Test in Docker Container

```bash
# 7. Navigate to docker directory
cd infra/docker

# 8. Run script in container
docker-compose run --rm pipeline-runner python etl/ingest_goalie_stats.py

# 9. Access database
docker-compose exec postgres psql -U postgres -d postgres

# 10. Run a query
docker-compose exec postgres psql -U postgres -d postgres -c "SELECT * FROM bet_log ORDER BY created_at DESC LIMIT 5;"
```

### Evening Cleanup

```bash
# 11. Stop services
docker-compose down

# Expected output:
# Stopping nhl_pgadmin... done
# Stopping nhl_postgres... done
# Removing nhl_pgadmin... done
# Removing nhl_postgres... done
```

---

## Quick Decision Tree

**"What should I run this morning?"**

```
Are you coding/debugging today?
├─ YES → Run: nhl-start (keeps postgres running, code locally)
└─ NO → Run: nhl-start (then use Docker for scheduled tasks)

Are you testing for production/deployment?
├─ YES → Run: cdd && dcu (start full stack)
└─ NO → Keep using local Python

Are you done for the day?
├─ Want to save RAM → Run: nhl-stop
└─ Coming back soon → Leave postgres running
```

---

## Troubleshooting Common Issues

### Issue: Aliases don't work

```bash
# Check if .bashrc is loaded
echo $PS1
# If blank or simple, run:
source ~/.bashrc

# Test alias
type nhl-start
# Should show: nhl-start is aliased to...
```

### Issue: Docker services won't start

```bash
# Check if Docker Desktop is running
docker --version
# If error, start Docker Desktop application

# Check what's running
docker ps -a

# Remove stopped containers
docker-compose down
docker-compose up -d
```

### Issue: Can't connect to database

```bash
# From local Python scripts:
# Check DATABASE_URL in pipelines/.env
cat pipelines/.env | grep DATABASE_URL
# Should point to Supabase or localhost:55432

# From Docker containers:
# Check postgres is healthy
docker-compose ps postgres
# STATUS should show "Up (healthy)"
```

### Issue: Python script errors

```bash
# Local Python missing dependencies?
cd pipelines
pip install -r requirements.txt

# Docker container missing dependencies?
cdd
docker-compose build --no-cache pipeline-runner
```

---

## Speed Comparison

| Task | Manual Commands | With Aliases | Time Saved |
|------|-----------------|--------------|------------|
| Start dev environment | `cd .../infra/docker && docker-compose up -d postgres pgadmin` | `nhl-start` | ~5 seconds |
| Run betting pipeline | `cd .../infra/docker && docker-compose run --rm pipeline-runner python betting/select_bets.py` | `nhl-bets` | ~10 seconds |
| Check container status | `cd .../infra/docker && docker-compose ps` | `nhl-status` | ~3 seconds |
| Connect to database | `docker-compose exec postgres psql -U postgres -d postgres` | `dpsql` | ~5 seconds |
| Navigate to docker dir | `cd "C:/Users/Nathan/Downloads/[My Projects]/nhl-betting-model/infra/docker"` | `cdd` | ~3 seconds |

**Total time saved per day: ~2-5 minutes**

---

## My Typical Day (Example)

```bash
# ========== MORNING (9 AM) ==========

# Open VSCode, start terminal
nhl-start           # Start postgres + pgAdmin
nhl-status          # Verify running

# ========== DEVELOPMENT (9 AM - 5 PM) ==========

# Work in VSCode/IDE
cd ~/Downloads/[My\ Projects]/nhl-betting-model/pipelines

# Code, test, repeat
vim betting/select_bets.py      # Edit code
python betting/select_bets.py    # Test locally (fast!)

# Check results
dpsql -c "SELECT COUNT(*) FROM bet_log;"

# More development...
vim etl/ingest_goalie_stats.py
python etl/ingest_goalie_stats.py

# ========== PRE-DEPLOYMENT TEST (4:30 PM) ==========

# Test in container before deploying
nhl-bets            # Run betting pipeline in Docker
nhl-ingest          # Run ingest in Docker

# ========== EVENING (5 PM) ==========

# Optional: Stop services or leave postgres running
nhl-stop            # Only if I want to free RAM

# ========== NEXT MORNING ==========

# Check if still running
nhl-status

# If stopped, restart
nhl-start
```

---

## Recommended Workflow for You

Based on your "bit of both script running and coding/debugging":

```bash
# ============================================
# MORNING ROUTINE (One command)
# ============================================
nhl-start


# ============================================
# ACTIVE DEVELOPMENT (Repeat all day)
# ============================================

# 1. Navigate to work directory
cd ~/Downloads/[My\ Projects]/nhl-betting-model/pipelines

# 2. Edit code in IDE
# (Use VSCode/IntelliJ file explorer)

# 3. Test locally (FAST - no container overhead)
python betting/select_bets.py
python pricing/compute_edges.py

# 4. Check database
dpsql -c "SELECT * FROM edges ORDER BY created_at DESC LIMIT 5;"


# ============================================
# BEFORE COMMITTING CODE (Validation)
# ============================================

# Test in container (matches production)
nhl-bets
# or
cdd && dpy betting/select_bets.py


# ============================================
# EVENING ROUTINE (Optional)
# ============================================
nhl-stop
# OR just close terminal (postgres stays running)
```

**This gives you:**
- ✅ Fast local iteration (no container overhead)
- ✅ Production validation before committing
- ✅ Simple commands (no long paths)
- ✅ Flexibility to switch between local and Docker

---

*Last Updated: 2026-05-20*
*Optimized for hybrid local + Docker development*

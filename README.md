# SA20 Pre-Season Intelligence Platform

A full-stack analytics platform for the SA20 cricket league featuring a FastAPI backend, machine learning services, and a React + TypeScript frontend.

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Docker Compose
```bash
docker-compose up --build
```

> **Note:** Run the ingestion + training steps above first so the containers mount populated `/app/data` artifacts (`team_feature_snapshot.csv`, model `.pkl` files, etc.).
> Backend API will be available at `http://localhost:8002`, frontend at `http://localhost:5173`, and Postgres will be exposed on `localhost:5435`.

## Fetching Sample Data

### Scraping SA20 Official Website Data
Scrape teams, players, statistics, and fixtures directly from the [SA20 official website](https://www.sa20.co.za):

```bash
# Inside Docker container
docker-compose exec backend python data_pipeline/scrape_all_sa20_data.py --season 2026 --export-stats-csv

# Or run individual scrapers:
# Scrape teams and players
docker-compose exec backend python data_pipeline/scrape_sa20_teams_players.py

# Scrape player statistics (batting/bowling leaders)
docker-compose exec backend python data_pipeline/scrape_sa20_stats.py --season 2026 --export-csv

# Scrape player profiles (birth dates, batting/bowling styles, season stats)
docker-compose exec backend python data_pipeline/scrape_player_profiles.py

# Scrape a single player profile (for testing)
docker-compose exec backend python data_pipeline/scrape_player_profiles.py --player "Corbin Bosch"

# Scrape with limit (e.g., first 10 players)
docker-compose exec backend python data_pipeline/scrape_player_profiles.py --limit 10

# Update all players including those with existing data
docker-compose exec backend python data_pipeline/scrape_player_profiles.py --update-all

# Clean up players without valid images (removes players from previous seasons)
docker-compose exec backend python data_pipeline/cleanup_players_without_images.py --dry-run
docker-compose exec backend python data_pipeline/cleanup_players_without_images.py --execute

# Monitor scraping progress (with completion notification)
docker-compose exec backend python data_pipeline/monitor_scraping_completion.py --interval 30 --expected 113

# Or use the convenience script
./backend/data_pipeline/start_scraping_monitor.sh

# Check scraping status
docker-compose exec backend python data_pipeline/check_scraping_progress.py
./backend/data_pipeline/check_scraping_status.sh

# Scrape fixtures
docker-compose exec backend python data_pipeline/seed_database.py --use-scraper --season 2026
```

This will:
- Extract team information and player squads with photos and roles
- Scrape batting and bowling statistics for each season and all-time
- Fetch actual match fixtures from the official schedule
- Export statistics to CSV files for ML model training

### Cricsheet Data Ingestion
A general ingestion tool ingests Cricsheet archives and materialises deliveries, rosters, and player master tables under `data/processed/`.

```bash
# create (or reuse) the backend virtualenv
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt

# ingest SA20 by default
backend/.venv/bin/python -m backend.data_pipeline.ingest_cricsheet

# include extra competitions (e.g., IPL and BBL)
backend/.venv/bin/python -m backend.data_pipeline.ingest_cricsheet --competitions sa20,ipl,bbl,it20s
```

Outputs:
- `data/processed/cricsheet_deliveries.csv` (all competitions)
- `data/processed/{competition}_deliveries.csv`
- `data/processed/cricsheet_team_rosters.csv`
- `data/processed/cricsheet_players.csv`

Use `--overwrite` to force re-download/extraction.

### Build Aggregated Tables
Aggregate deliveries into match scorecards plus player/team seasonal stats:

```bash
backend/.venv/bin/python -m backend.data_pipeline.build_aggregates
```

Outputs:
- `data/processed/match_scorecards.csv`
- `data/processed/team_season_stats.csv`
- `data/processed/player_season_stats.csv`

### Train Match Outcome Model
Train the gradient boosting classifier and export serving artifacts:

```bash
backend/.venv/bin/python -m backend.app.ml.training.train_match_model
```

Artifacts:
- `data/models/match_predictor.pkl`
- `data/models/match_predictor_features.json`
- `data/processed/team_feature_snapshot.csv`

### Train Player Performance Models
Generate batting (runs) and bowling (wickets) regressors and feature snapshots:

```bash
backend/.venv/bin/python -m backend.app.ml.training.train_player_models
```

Artifacts:
- `data/models/player_runs_regressor.pkl`
- `data/models/player_runs_features.json`
- `data/models/player_wickets_regressor.pkl`
- `data/models/player_wickets_features.json`
- `data/processed/player_feature_snapshot.csv`

### Access Aggregated Analytics via API
FastAPI (http://localhost:8002) now exposes pre-computed analytics under `/api/analytics`:

- `GET /api/analytics/team-stats?competition=sa20&season=2024/25`
- `GET /api/analytics/player-stats?competition=sa20&min_matches=3`
- `GET /api/analytics/match-scorecards?competition=sa20&limit=50`
- `GET /api/analytics/leaderboards/batting?competition=sa20&limit=10`
- `GET /api/analytics/leaderboards/bowling?competition=sa20&limit=10`
- `GET /api/analytics/head-to-head?team_a=MI%20Cape%20Town&team_b=Paarl%20Royals`

The React frontend (Season Predictor & Squad Analyzer) consumes these endpoints to surface historical context.

Player performance projections are available via `GET /api/players/{player_id}/projection`.

## Project Structure
```
backend/
  app/
    api/
    core/
    db/
    ml/
    schemas/
    services/
  data_pipeline/
    ingest_cricsheet.py
    scrapers/
frontend/
  src/
    api/
    components/
    features/
    types/
    utils/
```

## Environment Variables
- Copy `backend/.env.example` to `backend/.env`
- Copy `frontend/.env.example` to `frontend/.env`

## License
MIT

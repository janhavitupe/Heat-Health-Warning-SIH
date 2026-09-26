# Heat-Health Early Warning Platform

SIH 2026 · Problem Statement 26083 · Pilot city: Ahmedabad (48 wards)

A hyper-local platform that converts weather forecasts into ward-level thermal stress, population vulnerability, and mortality/hospitalization risk, then into targeted alerts and actions for authorities.

- Proposal: [Heat_Health_Project_Proposal.md](Heat_Health_Project_Proposal.md)
- Development phases: [phases/](phases/README.md)
- Data inventory: [data/README.md](data/README.md)
- Model configuration: [config.yaml](config.yaml)

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; use .venv/bin/activate elsewhere
pip install -e ".[dev]"
pytest

# Daily ward forecast with alert probabilities
python scripts/run_forecast.py

# API + ward map (see docs/api_map_phase5.md)
pip install -e ".[api]"
python -m api.cli all
cd frontend && npm install && npm run build && cd ..
HEAT_SCHEDULER=1 uvicorn api.main:app       # http://127.0.0.1:8000
```

## Layout

```
config.yaml       all weights and thresholds
heatrisk/         core scoring library
scripts/          data fetch and build scripts
gee/              Google Earth Engine exports
data/             raw, manual, and processed data
tests/            unit and data tests
docs/             status report, calibration, backtest, changelog
backtest/         May 2024 replay, sensitivity analysis, forecast skill, results
resources/        action rules and advisory templates (Phase 6)
api/              FastAPI service, SQLite storage, scheduled refresh
frontend/         React + MapLibre ward map
phases/           development plan
```

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
backtest/         May 2024 replay, sensitivity analysis, results
phases/           development plan
api/ frontend/    (later phases)
```

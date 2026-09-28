#!/bin/sh
# Container start-up: make sure the database has what the app needs, then start the server.
#
#   1. ward table (always refreshed from the image's data files)
#   2. May 2024 replay, if it is not built yet        (~1 min, needs internet)
#   3. first live forecast, if there is none            (~10 s, needs internet)
#   4. HEAT_DEMO=1: demo copy with labelled synthetic reports and scripted (simulated)
#      approvals, served instead of the working database (see scripts/demo_setup.py)
#   5. live ensemble probabilities in the background, if there are none (~4 min)
#
# Steps 2, 3 and 5 are skipped with a warning if the weather service can't be reached;
# the server still starts and the scheduler retries every hour.
set -u
APP="${APP_DIR:-/app}"; cd "$APP"
DATA="$APP/data/api"
mkdir -p "$DATA"
export HEAT_DB="$DATA/heat.db"

if [ -z "${HEAT_API_TOKEN:-}" ]; then
  echo "WARNING: HEAT_API_TOKEN is not set - anyone who can open the site can approve alerts and submit reports." >&2
fi

has() {  # has <sql>  -> exit 0 when the query returns a row
  python - "$1" <<'EOF'
import sqlite3, sys, os
try:
    c = sqlite3.connect(os.environ["HEAT_DB"])
    sys.exit(0 if c.execute(sys.argv[1]).fetchone() else 1)
except sqlite3.Error:
    sys.exit(1)
EOF
}

echo "[start] loading wards"
python -m api.cli wards || { echo "ward table failed to load" >&2; exit 1; }

if ! has "SELECT 1 FROM runs WHERE kind='replay' AND name='may2024' AND status='ok'"; then
  echo "[start] building the May 2024 replay (about a minute)"
  python -m api.cli replay may2024 || echo "WARNING: replay build failed (no internet?) - the demo view will be empty" >&2
fi

if ! has "SELECT 1 FROM runs WHERE kind='forecast' AND status='ok'"; then
  echo "[start] first live forecast"
  python -m api.cli forecast || echo "WARNING: forecast failed - the scheduler will retry" >&2
fi

if [ "${HEAT_DEMO:-0}" = "1" ]; then
  if [ ! -f "$DATA/demo.db" ] || [ "${HEAT_DEMO_RESET:-0}" = "1" ]; then
    echo "[start] preparing demo data (synthetic reports, simulated approvals)"
    HEAT_DISPATCH_MODE=simulated python scripts/demo_setup.py --no-pdf || echo "WARNING: demo setup failed" >&2
  fi
  [ -f "$DATA/demo.db" ] && export HEAT_DB="$DATA/demo.db"
fi

if ! has "SELECT 1 FROM runs WHERE kind='ensemble' AND status='ok'"; then
  echo "[start] live ensemble probabilities in the background (~4 min)"
  python -m api.cli ensemble >/tmp/ensemble.log 2>&1 &
fi

echo "[start] serving on port ${PORT:-8000} (database: $HEAT_DB)"
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"

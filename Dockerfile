# One image: builds the map (Node) and runs the API + scheduler (Python), serving both on $PORT (default 8000).
# The May 2024 demo is built into the image; start-up (docker/entrypoint.sh) only fetches live forecasts.
# Deployment guide: DEPLOY.md

FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HEAT_SCHEDULER=1 PORT=8000 TZ=Asia/Kolkata
COPY pyproject.toml README.md ./
COPY heatrisk/ heatrisk/
COPY api/ api/
RUN pip install --no-cache-dir -e ".[api]"
COPY config.yaml ./
COPY resources/ resources/
COPY data/processed/ data/processed/
COPY data/manual/ data/manual/
COPY backtest/results/may2024_city.csv backtest/results/may2024_city.csv
COPY scripts/demo_setup.py scripts/demo_setup.py
COPY docker/entrypoint.sh /entrypoint.sh
COPY --from=frontend /app/frontend/dist frontend/dist
# Build the May 2024 replay and the demo copy into the image (weather inputs are committed, so no
# internet is needed). Start-up is then instant, which small free hosts need.
RUN mkdir -p data/api \
 && HEAT_DB=/app/data/api/heat.db python -m api.cli wards \
 && HEAT_DB=/app/data/api/heat.db python -m api.cli replay may2024 \
 && HEAT_DISPATCH_MODE=simulated python scripts/demo_setup.py --no-pdf
# Writable database folder, so the container also works when a host runs it as a non-root user
RUN mkdir -p data/api && chmod -R a+rwX data /entrypoint.sh && sed -i 's/\r$//' /entrypoint.sh
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=10s --start-period=300s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/status' % os.environ.get('PORT', '8000'), timeout=8)"
CMD ["/bin/sh", "/entrypoint.sh"]

# One image: builds the map (Node) and runs the API + scheduler (Python), serving both on $PORT (default 8000).
# Start-up (docker/entrypoint.sh) builds the May 2024 replay and first forecast if missing.
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
# Writable database folder, so the container also works when a host runs it as a non-root user
RUN mkdir -p data/api && chmod -R a+rwX data /entrypoint.sh && sed -i 's/\r$//' /entrypoint.sh
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=10s --start-period=300s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/status' % os.environ.get('PORT', '8000'), timeout=8)"
CMD ["/bin/sh", "/entrypoint.sh"]

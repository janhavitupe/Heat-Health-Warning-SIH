# One image: builds the map (Node) and runs the API + scheduler (Python), serving both on :8000.
# Untested in the development environment (Docker not installed there) - see docs/api_map_phase5.md.

FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HEAT_SCHEDULER=1 HEAT_DB=/app/data/api/heat.db
COPY pyproject.toml README.md ./
COPY heatrisk/ heatrisk/
COPY api/ api/
RUN pip install --no-cache-dir -e ".[api]"
COPY config.yaml ./
COPY data/processed/ data/processed/
COPY data/manual/ data/manual/
COPY --from=frontend /app/frontend/dist frontend/dist
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

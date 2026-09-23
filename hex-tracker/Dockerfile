# ---- Frontend build stage ----
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Backend runtime stage ----
FROM python:3.12-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/app ./app

# The built frontend is served by the backend itself (see app/main.py) —
# one container, one process, no separate static-file server.
COPY --from=frontend-build /app/frontend/dist ./static

# Overridden by `-e DATABASE_URL=...` for Postgres; SQLite here needs a
# volume at /data to persist across container restarts (see README).
ENV DATABASE_URL=sqlite:////data/hex_tracker.db

EXPOSE 8000
# No curl/wget in the slim base image, so use Python (already present) to
# hit /health for Compose's `service_healthy` condition and orchestrators
# generally.
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health', timeout=2)" || exit 1
# --frozen --no-dev here too: without them, `uv run` re-syncs against the
# full dependency set (including dev-only deps like pytest) on every
# container start — needless network access, and non-deterministic if that
# network isn't there.
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

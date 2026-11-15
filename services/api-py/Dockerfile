# One image, two entrypoints:
#   api:    uvicorn app.main:app --host 0.0.0.0 --port 8000   (default CMD)
#   worker: python -m app.worker
# Build context: services/api-py.  Contains Chromium (PDF worker) and the
# Swiss Ephemeris data files (swiss is the default ephemeris provider).
FROM python:3.13-slim-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir ".[swiss]" uvicorn fastapi jinja2 \
       playwright azure-storage-blob

FROM python:3.13-slim-bookworm
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    ANKANA_SE_EPHE_PATH=/app/ephe \
    STORAGE_LOCAL_DIR=/data/storage
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
# Chromium plus its system libraries (shared by the API image so one tag serves both).
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY scripts ./scripts
# Swiss Ephemeris data files (sepl/semo/seas, 1800-2399).
RUN python scripts/fetch_ephe.py
RUN useradd --create-home --uid 10001 ankana \
    && mkdir -p /data/storage && chown -R ankana /data /app/ephe
USER ankana
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

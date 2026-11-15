# Ankana API (FastAPI) + worker image. Build context: repo root.
#   docker build -f infra/docker/api.Dockerfile \
#     --build-arg GIT_SHA=$(git rev-parse HEAD) -t ankana-api .
# The same image runs the API, the worker (different command) and alembic.
FROM python:3.13-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY services/api-py/pyproject.toml services/api-py/LICENSING.md ./
COPY services/api-py/src ./src
# azure-identity: managed-identity blob access (user-delegation SAS) and Key Vault keys.
# azure-communication-email: the reminder email channel (NOTIFY_EMAIL_BACKEND=acs).
# azure-keyvault-keys: optional Key Vault master key (ANKANA_KEYVAULT_KEY_ID).
RUN pip install --no-cache-dir --prefix=/install ".[swiss,observability,azure-identity]" \
    azure-communication-email azure-keyvault-keys
# Swiss Ephemeris data files (1800-2399). Without them pyswisseph silently falls
# back to the lower-accuracy Moshier ephemeris, so the build fails if they are missing.
COPY services/api-py/scripts/fetch_ephe.py ./fetch_ephe.py
RUN mkdir -p /ephe-build/scripts && cp fetch_ephe.py /ephe-build/scripts/ \
    && python /ephe-build/scripts/fetch_ephe.py \
    && test -s /ephe-build/ephe/sepl_18.se1 && test -s /ephe-build/ephe/semo_18.se1 \
    && test -s /ephe-build/ephe/seas_18.se1

FROM python:3.13-slim
ARG GIT_SHA=unknown
ARG SOURCE_URL=https://github.com/mrigankad/Ankana
ENV PYTHONUNBUFFERED=1 \
    API_ENV=production \
    ANKANA_EPHEMERIS=swiss \
    ANKANA_SE_EPHE_PATH=/opt/ephe \
    LAL_KITAB_DATA_DIR=/opt/lal-kitab-data \
    ANKANA_GIT_SHA=${GIT_SHA} \
    RELEASE_SHA=${GIT_SHA} \
    ANKANA_SOURCE_URL=${SOURCE_URL}
RUN useradd --create-home --uid 10001 ankana
COPY --from=build /install /usr/local
# Chromium for the PDF report worker (same image serves api, worker and migrate job).
RUN apt-get update && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* && chmod -R a+rX /ms-playwright
COPY --from=build /ephe-build/ephe /opt/ephe
COPY packages/lal-kitab/data /opt/lal-kitab-data
WORKDIR /app
COPY services/api-py/alembic.ini ./
COPY services/api-py/alembic ./alembic
COPY services/api-py/scripts/set_app_role_password.py ./scripts/set_app_role_password.py
COPY services/api-py/src ./src
# AGPL-3.0 section 13: ship the licence and source pointer with the image.
COPY LICENSE services/api-py/LICENSING.md ./
COPY --chmod=0755 infra/docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh
RUN mkdir -p data && chown -R ankana:ankana /app
USER ankana
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"
ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

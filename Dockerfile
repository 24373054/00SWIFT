FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json ./package.json
COPY frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json ./
COPY frontend/vite.config.ts frontend/index.html ./
COPY frontend/src ./src
RUN npm install --no-audit --no-fund \
    && npm run typecheck \
    && npm run test \
    && npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SWIFT_ENV=sandbox \
    HOST=0.0.0.0 \
    PORT=8765

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY --chown=app:app backend /app/backend
COPY --chown=app:app frontend /app/frontend
COPY --from=frontend-build --chown=app:app /app/frontend/dist /app/frontend/dist

RUN mkdir -p /app/backend/certs /app/data && chown -R app:app /app
USER app

EXPOSE 8765
VOLUME ["/app/data", "/app/backend/certs"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/ready', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]

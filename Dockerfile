# --- Stage 1: build the React frontend -------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: python runtime ---------------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    COMET_DATA_DIR=/data \
    COMET_STATIC_DIR=/app/static \
    COMET_PORT=8080

WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --upgrade pip && pip install .

COPY --from=frontend /build/dist ./static

RUN adduser --disabled-password --gecos "" comet \
    && mkdir -p /data && chown -R comet:comet /data /app
USER comet

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/api/health').status==200 else 1)"

CMD ["python", "-m", "app.main"]

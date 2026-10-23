FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARC_ROOT=/app \
    ARC_MODELS=/models \
    ARC_REPORTS=/app/reports

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY config ./config
COPY knowledge ./knowledge
COPY world ./world
COPY reports ./reports

RUN useradd --uid 10001 --create-home arc && mkdir -p /models && chown arc /models
USER arc

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s CMD curl -fsS localhost:8000/health || exit 1
CMD ["arc", "serve", "--host", "0.0.0.0", "--port", "8000"]

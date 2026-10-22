FROM debian:13.5-slim@sha256:28de0877c2189802884ccd20f15ee41c203573bd87bb6b883f5f46362d24c5c2 AS python-base

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        python3=3.13.5-1 \
        python3-numpy=1:2.2.4+ds-1 \
        python3-pandas=2.2.3+dfsg-9 \
        python3-pip \
        python3-venv \
    && python3 -m venv --system-site-packages /opt/venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY weighted_knn_genotype /app/weighted_knn_genotype
COPY backend /app/backend
COPY alembic.ini /app/alembic.ini

RUN pip install --no-cache-dir ".[backend]"

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data/jobs /data/uploads \
    && chown -R app:app /data


FROM python-base AS api

LABEL org.opencontainers.image.title="Shrimp Identification API"
LABEL org.opencontainers.image.version="0.3.0"
LABEL org.opencontainers.image.description="FastAPI task API for shrimp germplasm identification"

RUN mkdir -p /app/reference-data/panel-v1
COPY reference-data/panel-v1/manifest.json /app/reference-data/panel-v1/manifest.json
COPY reference-data/germplasm-name-map.json /app/reference-data/germplasm-name-map.json

USER app

EXPOSE 8000

ENTRYPOINT ["uvicorn", "backend.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]


FROM python-base AS worker

LABEL org.opencontainers.image.title="Shrimp Identification Worker"
LABEL org.opencontainers.image.version="0.3.0"
LABEL org.opencontainers.image.description="PLINK 1.9 and weighted-KNN asynchronous worker"

USER root

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        plink1.9=1.90~b7.7-241022-2 \
    && ln -s /usr/bin/plink1.9 /usr/local/bin/plink \
    && rm -rf /var/lib/apt/lists/*

ENV SHRIMP_REFERENCE_DIR=/app/reference-data/panel-v1

COPY reference-data/panel-v1 /app/reference-data/panel-v1

RUN chmod -R a-w /app/reference-data/panel-v1

USER app

ENTRYPOINT ["python3", "-m", "backend.worker"]


FROM worker AS analysis

LABEL org.opencontainers.image.title="Shrimp Germplasm Identification"
LABEL org.opencontainers.image.version="0.3.0"
LABEL org.opencontainers.image.description="PLINK 1.9 and weighted KNN germplasm identification"

WORKDIR /work

ENTRYPOINT ["python3", "-m", "weighted_knn_genotype"]
CMD ["--help"]

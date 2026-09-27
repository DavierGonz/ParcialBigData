FROM python:3.10.20-slim-bookworm@sha256:019e31cc1f52e4139d338bca44f27b71339a9da261738fd80fab9cf4595152fc
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
ENV PYTHONPATH=/app
COPY requirements/dask.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd --uid 10001 --create-home app && mkdir -p /data /scratch && chown app:root /data /scratch && chmod 2775 /data
COPY scripts/check_dask.py /opt/check_dask.py
COPY ingestion /app/ingestion
USER app:0
WORKDIR /app

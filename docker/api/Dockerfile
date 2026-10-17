FROM python:3.10.20-slim-bookworm@sha256:019e31cc1f52e4139d338bca44f27b71339a9da261738fd80fab9cf4595152fc AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements/api.txt /tmp/requirements.txt
COPY requirements/mongo.txt /tmp/mongo.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd --uid 10001 --create-home app
COPY api /app/api
COPY scripts/smoke_api.py /app/scripts/smoke_api.py
COPY scripts/smoke_geo.py /app/scripts/smoke_geo.py
COPY scripts/smoke_ui.py /app/scripts/smoke_ui.py

FROM base AS test
COPY benchmark /app/benchmark
COPY webhook /app/webhook
COPY requirements/dev.txt /tmp/dev.txt
RUN pip install --no-cache-dir -r /tmp/dev.txt
COPY tests /app/tests
COPY tests_api_integration /app/tests_api_integration
COPY pytest.ini /app/pytest.ini
COPY ci/faults /app/ci/faults
USER app
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS runtime
USER app
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "2", "--access-logfile", "-", "--error-logfile", "-", "api.wsgi:app"]

FROM python:3.10.20-slim-bookworm@sha256:019e31cc1f52e4139d338bca44f27b71339a9da261738fd80fab9cf4595152fc
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements/api.txt requirements/mongo.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/api.txt && useradd --uid 10001 --create-home app && mkdir /state && chown app:root /state
COPY webhook /app/webhook
USER app:0
CMD ["gunicorn", "--bind", "0.0.0.0:8090", "--workers", "1", "--threads", "2", "--access-logfile", "-", "webhook:create_app()"]

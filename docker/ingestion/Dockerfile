FROM parcialbigdata-dask:phase1 AS runtime
CMD ["python", "-m", "ingestion.run"]

FROM runtime AS test
ENV PYTEST_ADDOPTS="-p no:cacheprovider"
USER root
COPY requirements/dev.txt /tmp/dev.txt
COPY requirements/mongo.txt /tmp/mongo.txt
RUN pip install --no-cache-dir -r /tmp/dev.txt
COPY tests_ingestion /app/tests_ingestion
COPY benchmark /app/benchmark
COPY tests_benchmark /app/tests_benchmark
USER app:0
CMD ["python", "-m", "pytest", "tests_ingestion", "tests_benchmark", "-q", "--junitxml=/tmp/ingestion-tests.xml"]

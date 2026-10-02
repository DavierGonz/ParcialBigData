FROM spark:3.5.8-java17-python3@sha256:5363cd7d22758958565206f67a764356ebebb9fa8f5721e9c55aa86a78efafda
USER root
COPY requirements/spark.txt requirements/mongo.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/spark.txt
COPY docker/spark/install_connector.py /tmp/install_connector.py
RUN python3 /tmp/install_connector.py && mkdir -p /data /scratch && chown -R 185:0 /data /scratch && chmod 2775 /data
COPY docker/spark/spark-defaults.conf /opt/spark/conf/spark-defaults.conf
COPY scripts/check_spark.py /opt/check_spark.py
COPY scripts/smoke_spark.py /opt/smoke_spark.py
COPY processing /opt/processing
COPY benchmark /opt/benchmark
COPY tests_processing /opt/tests_processing
ENV PYTHONPATH=/opt
ENV SPARK_DAEMON_MEMORY=256m SPARK_LOCAL_DIRS=/scratch PYSPARK_PYTHON=python3
USER 185:0

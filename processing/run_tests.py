import sys
import fcntl
import pytest
from pyspark.sql import SparkSession
from processing.storage import configure_session

lock=open('/data/.ingestion.lock','r')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
spark=configure_session(SparkSession.builder.appName('phase4-known-data-tests')).getOrCreate()
spark.sparkContext.setLogLevel('WARN')
try:
    result=pytest.main(['/opt/tests_processing','-q','-p','no:cacheprovider','--junitxml=/scratch/spark-tests.xml'])
finally:
    spark.stop()
    lock.close()
sys.exit(result)

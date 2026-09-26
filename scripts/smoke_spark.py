"""Infrastructure check only: connector read of an empty collection, no ETL."""
import os
from urllib.parse import quote_plus
from pyspark.sql import SparkSession

database = os.environ['MONGO_DATABASE']
uri = ('mongodb://' + quote_plus(os.environ['MONGO_APP_USERNAME']) + ':'
       + quote_plus(os.environ['MONGO_APP_PASSWORD']) + '@mongodb:27017/' + database)
spark = (SparkSession.builder.appName('phase1-connector-smoke')
         .config('spark.mongodb.read.connection.uri', uri)
         .config('spark.mongodb.read.database', database)
         .config('spark.mongodb.read.collection', 'accidents').getOrCreate())
try:
    frame = spark.read.format('mongodb').schema('_id string').load()
    frame.limit(1).collect()
    print('PASS: Spark worker executed a MongoDB connector read (no writes).')
finally:
    spark.stop()

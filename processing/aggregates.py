from pyspark.sql import functions as F
from pyspark.sql.window import Window

METHOD_VERSION = 'grid01-civil-time-v1'
CELL_DEGREES = 0.1


def prepare(frame):
    # No timezone conversion: group the civil date/time recorded at the source.
    timestamp = F.try_to_timestamp(F.substring('Start_Time',1,19), F.lit('yyyy-MM-dd HH:mm:ss'))
    return (frame.withColumn('event_time', timestamp)
            .withColumn('cell_x', F.least(F.lit(3599),F.floor((F.col('Start_Lng')+180)*10)).cast('int'))
            .withColumn('cell_y', F.least(F.lit(1799),F.floor((F.col('Start_Lat')+90)*10)).cast('int')))


def aggregate(frame, run_id):
    grid = (frame.groupBy('cell_x','cell_y').count()
            .withColumn('run_id',F.lit(run_id))
            .withColumn('_id', F.concat_ws(':',F.lit(run_id),F.lit('grid'),F.col('cell_x'),F.col('cell_y')))
            )
    grid = (grid.withColumn('min_lon',F.col('cell_x')/10-180)
            .withColumn('min_lat',F.col('cell_y')/10-90)
            .withColumn('max_lon',(F.col('cell_x')+1)/10-180)
            .withColumn('max_lat',(F.col('cell_y')+1)/10-90))
    buckets = F.array(*[F.struct(F.lit(kind).alias('granularity'),F.date_format('event_time',pattern).alias('bucket'))
                         for kind,pattern in [('hour','HH'),('day','yyyy-MM-dd'),('month','yyyy-MM')]])
    temporal = (frame.filter(F.col('event_time').isNotNull()).select(F.explode(buckets).alias('t'))
                .select('t.*').groupBy('granularity','bucket').count()
                .withColumn('run_id',F.lit(run_id))
                .withColumn('_id',F.concat_ws(':',F.lit(run_id),F.col('granularity'),F.col('bucket'))))
    hotspots = (grid.orderBy(F.desc('count'),F.asc('cell_x'),F.asc('cell_y')).limit(50)
                .withColumn('rank',F.row_number().over(Window.orderBy(F.desc('count'),F.asc('cell_x'),F.asc('cell_y'))))
                )
    hotspots = hotspots.withColumn('_id', F.concat_ws(':',F.lit(run_id),F.lit('hotspot'),F.col('rank')))
    return {'grid':grid,'time':temporal,'hotspots':hotspots}

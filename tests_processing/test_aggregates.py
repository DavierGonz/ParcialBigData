import uuid

from pyspark.sql import SparkSession

from processing.aggregates import prepare,aggregate
from processing.storage import database, read_source, write_result, ensure_indexes, verify


def test_benchmark_grid_boundary_reference():
    from benchmark.common import cell, verify as compare
    points=[(-180.0,-90.0),(180.0,90.0),(-0.01,-0.01),(0.01,0.01),(0.02,0.02),(-118.3,34.0)]
    spark=SparkSession.builder.getOrCreate()
    source=spark.createDataFrame([(lon,lat,'2023-01-01 00:00:00') for lon,lat in points],['Start_Lng','Start_Lat','Start_Time'])
    result=aggregate(prepare(source),'boundary')['grid'].select('cell_x','cell_y','count').collect()
    expected={}
    for lon,lat in points:
        key=cell(lon,lat);expected[key]=expected.get(key,0)+1
    compare([(r.cell_x,r.cell_y,r['count']) for r in result],[(x,y,n) for (x,y),n in expected.items()])


def test_known_data_connector_aggregations_and_repeat():
    db=database()
    prefix='phase4_spark_test_'+uuid.uuid4().hex+'_'
    documents=[{'_id':str(i),'Start_Lat':lat,'Start_Lng':lon,'Start_Time':timestamp,'dataset_fingerprint':'test'}
               for i,(lat,lon,timestamp) in enumerate([
                   (0.01,0.01,'2023-01-01 01:00:00'),(0.02,0.02,'2023-01-01 01:20:00.123456789'),
                   (-0.01,-0.01,'2023-02-02 12:00:00'),(90.0,180.0,'2023-02-03 23:00:00'),
                   (0.03,0.03,'invalid')])]
    try:
        db[prefix+'source'].insert_many(documents)
        spark=SparkSession.builder.getOrCreate()
        source=read_source(spark,prefix+'source','test',partitions=2)
        frame=prepare(source)
        assert frame.count()==5
        results=aggregate(frame,'fixture')
        grid={(row.cell_x,row.cell_y):row['count'] for row in results['grid'].collect()}
        assert grid=={(1800,900):3,(1799,899):1,(3599,1799):1}
        hours={row.bucket:row['count'] for row in results['time'].filter("granularity='hour'").collect()}
        assert hours=={'01':2,'12':1,'23':1}
        ensure_indexes(db,prefix)
        for _ in range(2):
            for name,result in results.items(): write_result(result,prefix+name)
            proof=verify(db,'fixture',5,1,prefix)
            assert proof['grid_groups']==3 and proof['temporal']['month']=={'groups':2,'total':4}
            assert proof['hotspots']==3 and proof['top_cell']['count']==3
        assert db[prefix+'grid'].count_documents({})==3
    finally:
        for name in db.list_collection_names():
            if name.startswith(prefix): db.drop_collection(name)
        db.client.close()

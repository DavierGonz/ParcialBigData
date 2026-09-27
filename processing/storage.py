import hashlib
import json
import os
from urllib.parse import quote_plus

from pymongo import MongoClient

from processing.aggregates import METHOD_VERSION, CELL_DEGREES


def database():
    name=os.environ['MONGO_DATABASE']
    return MongoClient('mongodb',username=os.environ['MONGO_APP_USERNAME'],
                       password=os.environ['MONGO_APP_PASSWORD'],authSource=name,serverSelectionTimeoutMS=15000)[name]


def uri():
    return ('mongodb://'+quote_plus(os.environ['MONGO_APP_USERNAME'])+':'+quote_plus(os.environ['MONGO_APP_PASSWORD'])
            +'@mongodb:27017/'+os.environ['MONGO_DATABASE'])


def configure_session(builder):
    return (builder.config('spark.mongodb.read.connection.uri',uri())
            .config('spark.mongodb.write.connection.uri',uri())
            .config('spark.sql.session.timeZone','UTC'))


def read_source(spark, collection, fingerprint, partitions=8):
    pipeline=[{'$match':{'dataset_fingerprint':fingerprint}},
              {'$project':{'_id':1,'Start_Lat':1,'Start_Lng':1,'Start_Time':1}}]
    return (spark.read.format('mongodb')
            .option('database',os.environ['MONGO_DATABASE']).option('collection',collection)
            .option('partitioner','com.mongodb.spark.sql.connector.read.partitioner.PaginateIntoPartitionsPartitioner')
            .option('partitioner.options.max.number.of.partitions',str(partitions))
            .option('aggregation.pipeline',json.dumps(pipeline))
            .option('aggregation.allowDiskUse','false')
            .schema('_id string, Start_Lat double, Start_Lng double, Start_Time string').load())


def write_result(frame, collection):
    (frame.write.format('mongodb').mode('append')
     .option('database',os.environ['MONGO_DATABASE']).option('collection',collection)
     .option('operationType','replace').option('idFieldList','_id').option('upsertDocument','true')
     .option('ordered','false').option('maxBatchSize','250').save())


def identity(fingerprint):
    return hashlib.sha256(f'{fingerprint}:{METHOD_VERSION}:{CELL_DEGREES}'.encode()).hexdigest()


def ensure_indexes(db, prefix='analytics_'):
    for kind in ('grid','hotspots'):
        db[prefix+kind].create_index([('run_id',1),('count',-1),('_id',1)])
    db[prefix+'time'].create_index([('run_id',1),('granularity',1),('bucket',1)],unique=True)


def verify(db, run_id, expected, invalid_time, prefix='analytics_'):
    match={'run_id':run_id}
    totals={}
    for name in ('grid','time'):
        group={'_id':'$granularity' if name=='time' else None, 'total':{'$sum':'$count'},'groups':{'$sum':1}}
        values=list(db[prefix+name].aggregate([{'$match':match},{'$group':group}],maxTimeMS=30000))
        totals[name]=values
    assert len(totals['grid'])==1 and totals['grid'][0]['total']==expected, 'Grid total differs from source'
    assert {v['_id'] for v in totals['time']}=={'hour','day','month'}
    assert all(v['total']==expected-invalid_time for v in totals['time']), 'Temporal totals differ from valid timestamps'
    top=list(db[prefix+'grid'].find(match,{'_id':0,'cell_x':1,'cell_y':1,'count':1})
             .sort([('count',-1),('cell_x',1),('cell_y',1)]).limit(50))
    actual=list(db[prefix+'hotspots'].find(match,{'_id':0,'cell_x':1,'cell_y':1,'count':1}).sort('rank',1))
    assert actual==top, 'Hotspots do not match the most concentrated grid cells'
    return {'grid_groups':totals['grid'][0]['groups'],'grid_total':expected,
            'temporal':{v['_id']:{'groups':v['groups'],'total':v['total']} for v in totals['time']},
            'hotspots':len(top),'top_cell':top[0]}

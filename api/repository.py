import os

from flask import current_app
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from werkzeug.exceptions import ServiceUnavailable, BadRequest

FIELDS = {'_id': 0, 'ID': 1, 'Severity': 1, 'Start_Time': 1, 'City': 1, 'State': 1,
          'location': 1, 'dataset_fingerprint': 1}
QUERY_MS = 3000


def configure(app):
    if 'DATABASE' in app.config:
        app.extensions['database'] = app.config['DATABASE']
    elif os.environ.get('MONGO_APP_PASSWORD'):
        name = os.environ.get('MONGO_DATABASE', 'us_accidents')
        client = MongoClient('mongodb', username=os.environ['MONGO_APP_USERNAME'],
                             password=os.environ['MONGO_APP_PASSWORD'], authSource=name,
                             serverSelectionTimeoutMS=2000, connectTimeoutMS=2000,
                             socketTimeoutMS=5000, maxPoolSize=10, connect=False)
        app.extensions['mongo_client'] = client
        app.extensions['database'] = client[name]


def database():
    if 'database' not in current_app.extensions:
        raise ServiceUnavailable('Database is not configured')
    return current_app.extensions['database']


def accidents():
    return database()[current_app.config.get('ACCIDENTS_COLLECTION', 'accidents')]


def near(point, radius, limit, distances=False):
    if distances:
        stages = [{'$geoNear': {'near': point, 'distanceField': 'distance_m', 'key': 'location',
                                'maxDistance': radius, 'spherical': True}},
                  {'$limit': limit+1}, {'$project': {**FIELDS, 'distance_m': 1}}]
        return list(accidents().aggregate(stages, maxTimeMS=QUERY_MS, allowDiskUse=False, batchSize=limit+1))
    query = {'location': {'$near': {'$geometry': point, '$maxDistance': radius}}}
    return list(accidents().find(query, FIELDS).limit(limit+1).max_time_ms(QUERY_MS))


def within(geometry, limit):
    try:
        return list(accidents().find({'location': {'$geoWithin': {'$geometry': geometry}}}, FIELDS)
                    .limit(limit+1).max_time_ms(QUERY_MS))
    except OperationFailure as error:
        if error.code in (2,16755):
            raise BadRequest('Polygon is not valid for spherical geometry') from None
        raise


def analytics(kind, limit, offset):
    db = database()
    prefix = current_app.config.get('ANALYTICS_PREFIX', 'analytics_')
    state = db[prefix+'state'].find_one({'_id': 'active'}, max_time_ms=QUERY_MS)
    if not state:
        raise ServiceUnavailable('Spark results are not published yet')
    run = db[prefix+'runs'].find_one({'_id':state['run_id'], 'status':'complete'}, {'_id':0}, max_time_ms=QUERY_MS)
    if not run:
        raise ServiceUnavailable('Spark run is not complete')
    collection = kind if kind in ('grid','hotspots') else 'time'
    query = {'run_id':state['run_id']}
    if collection == 'time':
        query['granularity'] = kind
        order = [('bucket',1)]
    else:
        order = [('count',-1),('_id',1)]
    rows = list(db[prefix+collection].find(query, {'_id':0}).sort(order).skip(offset).limit(limit+1).max_time_ms(QUERY_MS))
    return rows, {key:run[key] for key in ('run_id','source_fingerprint','source_rows','dataset_version','cell_degrees','time_basis')}

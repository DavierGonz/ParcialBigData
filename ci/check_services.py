"""Executed inside the Dask scheduler using its own dependencies."""
import os
from distributed import Client
from pymongo import MongoClient

with MongoClient('mongodb', username=os.environ['MONGO_APP_USERNAME'],
                 password=os.environ['MONGO_APP_PASSWORD'],
                 authSource=os.environ['MONGO_DATABASE'], serverSelectionTimeoutMS=5000) as mongo:
    mongo.admin.command('ping')
    collection = mongo[os.environ['MONGO_DATABASE']].accidents
    assert any(i['key'].get('location') == '2dsphere' for i in collection.list_indexes())
    assert collection.options()['validator']['$jsonSchema']['required'] == ['location']
    print('PASS: MongoDB authentication, GeoJSON validator and 2dsphere index')
with Client('tcp://dask-scheduler:8786', timeout='10s') as client:
    client.wait_for_workers(2, timeout=20)
    workers = client.scheduler_info()['workers']
    assert {w['name'] for w in workers.values()} == {'worker-1', 'worker-2'}
    futures = [client.submit(sum, [1, 2, 3], workers=[address], allow_other_workers=False, pure=False) for address in workers]
    assert client.gather(futures) == [6, 6]
    print('PASS: a real task executed on each Dask worker')

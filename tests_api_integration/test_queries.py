import os
import uuid

import pytest
from pymongo import MongoClient

from api import create_app


@pytest.fixture
def client():
    name=os.environ['MONGO_DATABASE']
    db=MongoClient('mongodb',username=os.environ['MONGO_APP_USERNAME'],password=os.environ['MONGO_APP_PASSWORD'],authSource=name)[name]
    prefix='phase4_api_test_'+uuid.uuid4().hex+'_'
    collection=prefix+'accidents'
    db[collection].create_index([('location','2dsphere')])
    db[collection].insert_many([{'_id':identifier,'ID':identifier,'location':{'type':'Point','coordinates':point}}
                               for identifier,point in [('a',[0,0]),('b',[0.001,0]),('outside',[1,1])]])
    app=create_app({'TESTING':True,'DATABASE':db,'ACCIDENTS_COLLECTION':collection,'ANALYTICS_PREFIX':prefix})
    try:
        yield app.test_client(),db,prefix
    finally:
        for name in db.list_collection_names():
            if name.startswith(prefix): db.drop_collection(name)
        db.client.close()


def test_real_near_and_distances(client):
    http,_,_=client
    near=http.get('/accidents/near?lat=0&lon=0&radius_m=200').json
    assert [row['ID'] for row in near['items']]==['a','b']
    limited=http.get('/accidents/near?lat=0&lon=0&radius_m=200&limit=1').json
    assert limited['count']==1 and limited['has_more']
    geo=http.get('/accidents/geo-near?lat=0&lon=0&radius_m=200').json
    assert geo['operator']=='$geoNear'
    assert geo['items'][0]['distance_m']==0
    assert 100 < geo['items'][1]['distance_m'] < 120


def test_real_polygon_and_empty(client):
    http,_,_=client
    geometry={'type':'Polygon','coordinates':[[[-.01,-.01],[.01,-.01],[.01,.01],[-.01,.01],[-.01,-.01]]]}
    response=http.post('/accidents/within',json={'geometry':geometry})
    assert response.status_code==200 and {r['ID'] for r in response.json['items']}=={'a','b'}
    assert http.get('/accidents/near?lat=30&lon=30&radius_m=1').json['count']==0


def test_only_published_analytics_and_pagination(client):
    http,db,prefix=client
    assert http.get('/analytics').status_code==503
    db[prefix+'state'].insert_one({'_id':'active','run_id':'run'})
    assert http.get('/analytics').status_code==503
    db[prefix+'runs'].insert_one({'_id':'run','run_id':'run','status':'complete','source_fingerprint':'fixture',
                                 'source_rows':3,'dataset_version':13,'cell_degrees':.1,'time_basis':'civil'})
    db[prefix+'grid'].insert_many([{'_id':str(i),'run_id':'run','count':i} for i in (1,2,3)])
    db[prefix+'grid'].insert_one({'_id':'unpublished','run_id':'other','count':999})
    result=http.get('/analytics?kind=grid&limit=1&offset=1').json
    assert result['items'][0]['count']==2 and result['has_more']
    assert result['source']['source_fingerprint']=='fixture'


def test_real_sample_and_analytics_coherence():
    app=create_app({'TESTING':True})
    http=app.test_client()
    try:
        response=http.get('/accidents/geo-near?lat=32.81517&lon=-116.914566&radius_m=1000&limit=3')
        assert response.status_code==200 and response.json['count']==3
        assert response.json['items'][0]['distance_m'] < 1
        for kind in ('grid','hotspots','hour','day','month'):
            result=http.get('/analytics?kind='+kind+'&limit=3')
            assert result.status_code==200 and result.json['count']==3
            assert result.json['source']['source_rows']==1103657
    finally:
        app.extensions['mongo_client'].close()

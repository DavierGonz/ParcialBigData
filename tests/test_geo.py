import pytest
from pymongo.errors import ExecutionTimeout, AutoReconnect

from api import create_app, repository


@pytest.fixture
def client():
    return create_app({'TESTING':True}).test_client()


@pytest.mark.parametrize('query',[
    '', 'lat=91&lon=0&radius_m=10', 'lat=0&lon=181&radius_m=10',
    'lat=nan&lon=0&radius_m=10','lat=0&lon=0&radius_m=inf',
    'lat=0&lon=0&radius_m=0','lat=0&lon=0&radius_m=50001',
    'lat=0&lon=0&radius_m=1&limit=101','lat=0&lon=0&radius_m=1&limit=1.5',
    'lat=0&lat=1&lon=0&radius_m=1','lat=0&lon=0&radius_m=1&$where=x',
    'lat=0&lon=0&radius_m=1&limit='+('9'*5000),
])
@pytest.mark.parametrize('route',['near','geo-near'])
def test_invalid_proximity(client,query,route):
    response=client.get('/accidents/'+route+'?'+query)
    assert response.status_code==400 and response.json['error']['code']==400


def test_proximity_contract_and_limit(client,monkeypatch):
    def near(point,radius,limit,distances=False):
        assert point=={'type':'Point','coordinates':[-80.0,35.0]}
        assert radius==1000 and limit==1
        return [{'ID':'a'},{'ID':'b'}]
    monkeypatch.setattr(repository,'near',near)
    response=client.get('/accidents/near?lat=35&lon=-80&radius_m=1000&limit=1')
    assert response.json=={'items':[{'ID':'a'}],'count':1,'has_more':True,'operator':'$near','radius_m':1000.0}


RING=[[0,0],[1,0],[1,1],[0,1],[0,0]]


@pytest.mark.parametrize('geometry',[
    None, {'type':'Point','coordinates':[0,0]},
    {'type':'Polygon','coordinates':[]},
    {'type':'Polygon','coordinates':[RING,RING]},
    {'type':'Polygon','coordinates':[RING[:-1]]},
    {'type':'Polygon','coordinates':[[[0,0],[1,0],[2,0],[0,0]]]},
    {'type':'Polygon','coordinates':[[[0,0],[2,2],[0,2],[2,0],[0,0]]]},
    {'type':'Polygon','coordinates':[[[0,0],[3,2],[0,3],[2,0],[0,0]]]},
    {'type':'Polygon','coordinates':[[[0,90],[1,90],[1,91],[0,90]]]},
    {'type':'Polygon','coordinates':[[[0,0],[6,0],[6,1],[0,0]]]},
    {'type':'Polygon','coordinates':[[[True,0],[1,0],[1,1],[True,0]]]},
    {'type':'Polygon','coordinates':[[['0',0],[1,0],[1,1],['0',0]]]},
    {'type':'Polygon','coordinates':[RING],'crs':{}},
])
def test_invalid_polygon(client,geometry):
    assert client.post('/accidents/within',json={'geometry':geometry}).status_code==400


def test_polygon_accepts_concave_ring(client,monkeypatch):
    geometry={'type':'Polygon','coordinates':[[[0,0],[2,0],[1,1],[2,2],[0,2],[0,0]]]}
    monkeypatch.setattr(repository,'within',lambda value,limit: [])
    response=client.post('/accidents/within',json={'geometry':geometry})
    assert response.status_code==200 and response.json['items']==[]


def test_http_errors_and_limits(client):
    assert client.get('/accidents/within').status_code==405
    assert client.post('/accidents/within',data='{}').status_code==415
    assert client.post('/accidents/within',data='{',content_type='application/json').status_code==400
    assert client.post('/accidents/within',data=' '*33000,content_type='application/json').status_code==413
    assert client.get('/analytics?kind=all').status_code==400
    assert client.get('/analytics?offset=10001').status_code==400


@pytest.mark.parametrize('error,code',[(ExecutionTimeout('private server detail'),504),(AutoReconnect('private detail'),503)])
def test_database_errors_are_sanitized(client,monkeypatch,error,code):
    def fail(*args): raise error
    monkeypatch.setattr(repository,'near',fail)
    response=client.get('/accidents/near?lat=0&lon=0&radius_m=100')
    assert response.status_code==code and 'private' not in response.get_data(as_text=True)

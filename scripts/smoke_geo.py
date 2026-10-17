"""Live HTTP checks against the deployed or candidate API; bounded public responses."""
import argparse
import json
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from smoke_ui import verify as verify_ui


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('base_url')
    args=parser.parse_args()
    verify_ui(args.base_url)
    def call(path,body=None):
        data=None if body is None else json.dumps(body).encode()
        request=Request(args.base_url.rstrip('/')+path,data=data,headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=10) as response:
            assert response.status==200
            return json.load(response)
    query='?lat=32.81517&lon=-116.914566&radius_m=1000&limit=2'
    for route,operator in [('/accidents/near','$near'),('/accidents/geo-near','$geoNear')]:
        result=call(route+query)
        assert result['count']==2 and result['operator']==operator
    polygon={'type':'Polygon','coordinates':[[[-116.93,32.80],[-116.90,32.80],[-116.90,32.83],[-116.93,32.83],[-116.93,32.80]]]}
    assert call('/accidents/within',{'geometry':polygon,'limit':2})['count']>0
    for kind in ('grid','hotspots','hour','day','month'):
        result=call('/analytics?kind='+kind+'&limit=2')
        assert result['count']==2 and result['source']['source_rows']>=1_000_000
    try:
        call('/accidents/near?lat=91&lon=0&radius_m=1')
    except HTTPError as error:
        assert error.code==400
    else:
        raise AssertionError('Invalid coordinates were accepted')
    print('PASS: live near, polygon, geoNear, Spark results and validation')


if __name__=='__main__': main()

import io
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.request
import zipfile

import pandas as pd
import pytest

from ingestion.download import SafeRedirect, authorization, download
from ingestion.etl import clean, document, selected, write_batch


def archive(name='accidents.csv', text='ID,Start_Lat,Start_Lng,Start_Time,Severity,State\nA-1,35,-80,2023-01-01,2,NC\n'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as zipped:
        zipped.writestr(name, text)
    return stream.getvalue()


class Response(io.BytesIO):
    def __init__(self, data, size=None):
        super().__init__(data)
        self.headers = {'Content-Length': str(len(data) if size is None else size)}


def source(payload=None, version=13, size=None):
    calls = []
    def open_url(url):
        calls.append(url)
        if '/view/' in url:
            return Response(json.dumps({'currentVersionNumber': version, 'lastUpdated': '2023-05-28',
                                        'licenseName': 'CC BY-NC-SA 4.0', 'totalBytes': 123}).encode())
        return Response(archive() if payload is None else payload, size)
    return open_url, calls


def test_download_cache_and_corruption(tmp_path):
    opener, calls = source()
    manifest, result = download(tmp_path, opener=opener)
    assert result['downloaded_bytes'] > 0 and not result['cache_hit']
    assert manifest['columns'][1:3] == ['Start_Lat', 'Start_Lng']
    assert manifest['version'] == 13 and len(manifest['artifacts']) == 2
    assert 'datasetVersionNumber=13' in calls[-1]
    cached, result = download(tmp_path, opener=opener)
    assert cached == manifest and result['cache_hit'] and len(calls) == 2
    (tmp_path / 'us-accidents-v13' / manifest['csv']).write_text('corrupt')
    _, result = download(tmp_path, opener=opener)
    assert not result['cache_hit'] and len(calls) == 4


@pytest.mark.parametrize('name', ['../outside.csv', 'folder/data.csv', '..\\outside.csv'])
def test_reject_unsafe_archive(tmp_path, name):
    opener, _ = source(archive(name))
    with pytest.raises(ValueError, match='Unsafe'):
        download(tmp_path, opener=opener)
    assert not (tmp_path / 'us-accidents-v13/manifest.json').exists()


def test_truncated_download_is_not_cached(tmp_path):
    opener, _ = source(size=999999)
    with pytest.raises(ValueError, match='Incomplete'):
        download(tmp_path, opener=opener)
    assert not (tmp_path / 'us-accidents-v13/manifest.json').exists()


def test_version_requires_review(tmp_path):
    opener, calls = source(version=14)
    with pytest.raises(ValueError, match='version changed'):
        download(tmp_path, opener=opener)
    assert len(calls) == 1


def test_schema_missing_columns(tmp_path):
    opener, _ = source(archive(text='ID,Latitude\n1,32\n'))
    with pytest.raises(ValueError, match='columns'):
        download(tmp_path, opener=opener)


def test_credential_and_redirect():
    with pytest.raises(ValueError, match='Missing'):
        authorization('')
    assert authorization('example-only') == 'Bearer example-only'
    assert authorization('{"username":"test","key":"example"}').startswith('Basic ')
    request = urllib.request.Request('https://www.kaggle.com/api', headers={'Authorization': 'Bearer example'})
    redirected = SafeRedirect().redirect_request(request, None, 302, '', {}, 'https://storage.googleapis.com/test')
    assert not redirected.has_header('Authorization')


def test_clean_disjoint_reasons_and_boundaries():
    frame = pd.DataFrame({'ID': ['a','b','c','d','e','f','g','h','i',''],
                          'Start_Lat': ['0','90','-90','','NaN','word','inf','91','30','30'],
                          'Start_Lng': ['0','180','-180','abc','0','0','0','181','-181','20']})
    result, counts = clean(frame)
    assert list(result.ID) == ['a', 'b', 'c']
    assert counts == {'read': 10, 'missing_coordinates': 2, 'invalid_coordinates': 2,
                      'out_of_range': 2, 'missing_id': 1, 'clean': 3}


def test_transform_order_nulls_and_civil_time():
    record = document({'ID': 'A-1', 'Start_Lat': 35, 'Start_Lng': -80, 'Severity': '2',
                       'End_Lat': None, 'Start_Time': '2023-01-01 12:00:00'}, 'fingerprint')
    assert record['location'] == {'type': 'Point', 'coordinates': [-80.0, 35.0]}
    assert record['_id'] == 'A-1' and record['End_Lat'] is None
    assert next(iter(record)) == '_id'
    assert record['Start_Time'] == '2023-01-01 12:00:00'


def test_sample_is_order_independent():
    identifiers = [f'A-{number}' for number in range(10000)]
    a = {value for value in identifiers if selected(value)}
    b = {value for value in reversed(identifiers) if selected(value)}
    assert a == b and 1200 < len(a) < 1700


def test_batched_upserts_use_source_identity():
    class Collection:
        def bulk_write(self, operations, ordered):
            assert ordered is False
            assert len(operations) == 2
            assert operations[0]._filter == {'_id': 'A-1'}
            assert operations[0]._upsert is True
            return SimpleNamespace(upserted_count=1, matched_count=1, modified_count=0)
    result = write_batch(Collection(), [{'_id': 'A-1'}, {'_id': 'A-2'}])
    assert result == {'inserted': 1, 'matched': 1, 'modified': 0}
    assert write_batch(None, [])['inserted'] == 0

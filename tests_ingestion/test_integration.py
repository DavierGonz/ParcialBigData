import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
import urllib.request
import uuid

import pandas as pd
import pytest

from ingestion.download import download, cache_lock
from tests_ingestion.test_unit import archive


def test_download_over_http(tmp_path):
    payload = archive()
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({'currentVersionNumber': 13, 'lastUpdated': '2023-05-28',
                               'licenseName': 'test', 'totalBytes': len(payload)}).encode() if '/view/' in self.path else payload
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def opener(url):
            path = url.split('/api/v1/', 1)[1]
            return urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/{path}', timeout=5)
        manifest, stats = download(tmp_path, opener=opener)
        assert stats['downloaded_bytes'] == len(payload)
        assert manifest['csv'] == 'accidents.csv'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.skipif(os.name == 'nt', reason='Cache lock runs in Linux containers')
def test_cache_concurrent_lock(tmp_path):
    with cache_lock(tmp_path):
        with pytest.raises(BlockingIOError):
            with cache_lock(tmp_path):
                pass


@pytest.mark.skipif(os.environ.get('RUN_INGESTION_INTEGRATION') != '1', reason='Requires Docker Dask and MongoDB')
def test_distributed_csv_mongo_idempotency():
    import dask.dataframe as dd
    from dask import delayed
    from distributed import Client
    from pymongo.errors import WriteError
    from ingestion.etl import database, process_partition, verify
    name = 'phase3_test_' + uuid.uuid4().hex
    db = database()
    with tempfile.TemporaryDirectory(prefix='phase3-test-', dir='/data') as temp:
        try:
            # Apply the actual production validator to the isolated test collection.
            options = db.accidents.options()
            db.create_collection(name, validator=options['validator'], validationLevel='strict')
            db[name].create_index([('location', '2dsphere')], name='location_2dsphere')
            frame = pd.DataFrame({'ID': ['test-1','test-2','bad'], 'Start_Lat': ['35','36','95'],
                                  'Start_Lng': ['-80','-81','-82'], 'Severity': ['2','3','1']})
            csv = Path(temp) / 'test.csv'
            frame.to_csv(csv, index=False)
            data = dd.read_csv(str(csv), dtype=str, blocksize=None, keep_default_na=False).to_delayed()[0]
            with Client('tcp://dask-scheduler:8786') as client:
                client.wait_for_workers(2, timeout=60)
                workers = sorted(client.scheduler_info()['workers'])
                first = client.compute(delayed(process_partition)(data, 'test', 1, name), workers=[workers[0]]).result()
                second = client.compute(delayed(process_partition)(data, 'test', 1, name), workers=[workers[1]], optimize_graph=False).result()
            assert first['inserted'] == 2 and first['out_of_range'] == 1
            assert second['inserted'] == 0 and second['matched'] == 2
            assert second['modified'] == 0
            assert first['worker'] != second['worker']
            proof = verify(db, 'test', minimum=2, collection_name=name)
            assert proof['stored'] == 2 and proof['total_collection'] == 2
            with pytest.raises(WriteError):
                db[name].insert_one({'_id': 'invalid', 'location': {'type': 'Point', 'coordinates': [181, 95]}})
        finally:
            db.drop_collection(name)
            db.client.close()

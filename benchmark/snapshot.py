"""Stream a read-only projection of the existing sample, once, under the ETL lock."""
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

from pymongo import MongoClient
from benchmark.common import EXPECTED_ROWS, FINGERPRINT, cell, digest


def main():
    root = Path('/data/benchmark-v1')
    with open('/data/.ingestion.lock', 'r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        name = os.environ['MONGO_DATABASE']
        with MongoClient('mongodb', username=os.environ['MONGO_APP_USERNAME'], password=os.environ['MONGO_APP_PASSWORD'], authSource=name) as client:
            db = client[name]
            assert db.accidents.count_documents({}) == EXPECTED_ROWS
            assert db.accidents.count_documents({'dataset_fingerprint': FINGERPRINT}) == EXPECTED_ROWS
            state = db.analytics_state.find_one({'_id':'active'})
            run = db.analytics_runs.find_one({'_id':state['run_id'], 'status':'complete'})
            assert run['source_fingerprint'] == FINGERPRINT
            golden = [(d['cell_x'], d['cell_y'], d['count']) for d in db.analytics_grid.find({'run_id':run['run_id']})]
            if (root/'manifest.json').exists():
                manifest = json.loads((root/'manifest.json').read_text())
                assert manifest['fingerprint'] == FINGERPRINT and manifest['rows'] == EXPECTED_ROWS
                assert manifest['grid_sha256'] == digest(golden)
                for entry in manifest['files']:
                    assert hashlib.sha256((root/entry['name']).read_bytes()).hexdigest() == entry['sha256']
                print('Verified existing benchmark snapshot'); return
            root.mkdir(exist_ok=True)
            start = time.perf_counter()
            paths = [root/f'part-{i:02}.csv' for i in range(8)]
            streams = [p.open('w', newline='') for p in paths]
            writers = [csv.writer(s) for s in streams]
            for writer in writers: writer.writerow(['ID','Start_Lng','Start_Lat','Start_Time'])
            ids = hashlib.sha256(); counts = [0]*8; reference = {}
            try:
                cursor = db.accidents.find({'dataset_fingerprint':FINGERPRINT}, {'Start_Lng':1,'Start_Lat':1,'Start_Time':1}).sort('_id',1).batch_size(1000)
                for i, doc in enumerate(cursor):
                    key = cell(doc['Start_Lng'], doc['Start_Lat'])
                    reference[key] = reference.get(key,0)+1
                    writers[i%8].writerow([doc['_id'],repr(doc['Start_Lng']),repr(doc['Start_Lat']),doc['Start_Time']])
                    ids.update((doc['_id']+'\n').encode()); counts[i%8] += 1
            finally:
                for stream in streams: stream.close()
            assert sum(counts) == EXPECTED_ROWS
            assert digest([(x,y,n) for (x,y),n in reference.items()]) == digest(golden)
            (root/'golden.json').write_text(json.dumps(sorted(golden)))
            manifest = {'rows':sum(counts),'fingerprint':FINGERPRINT,'dataset_version':run['dataset_version'],
                        'source_csv_sha256':run['source_csv_sha256'],'sorted_ids_sha256':ids.hexdigest(),
                        'grid_sha256':digest(golden),'files':[{'name':p.name,'rows':counts[i],'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for i,p in enumerate(paths)],
                        'preparation_seconds':time.perf_counter()-start}
            (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
            print(json.dumps(manifest))


if __name__ == '__main__': main()

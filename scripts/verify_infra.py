"""Run read-only infrastructure smoke checks through Docker Compose."""
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def compose(*args):
    result = subprocess.run(['docker', 'compose', *args], cwd=ROOT, text=True,
                            capture_output=True, timeout=120, check=True)
    return result.stdout.strip()


def main():
    raw = compose('ps', '--format', 'json')
    services = json.loads(raw) if raw.startswith('[') else [json.loads(line) for line in raw.splitlines()]
    expected = {'mongodb', 'spark-master', 'spark-worker', 'dask-scheduler',
                'dask-worker-1', 'dask-worker-2', 'api', 'jenkins'}
    running = {s['Service']: s for s in services}
    assert expected <= running.keys(), f'Missing services: {expected - running.keys()}'
    for name in sorted(expected):
        assert running[name].get('Health') == 'healthy', f'{name} is not healthy'
        print(f'PASS: {name} healthy')

    env = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
               if line and not line.startswith('#') and '=' in line)
    with urlopen(f"http://127.0.0.1:{env.get('API_PORT', '5000')}/health", timeout=5) as response:
        assert response.status == 200
        assert json.load(response) == {'status': 'ok', 'service': 'us-accidents-api'}
    print('PASS: API HTTP contract')

    mongo = '''
const c = new Mongo('mongodb://127.0.0.1:27017');
const d = c.getDB(process.env.MONGO_DATABASE);
if (!d.auth(process.env.MONGO_APP_USERNAME, process.env.MONGO_APP_PASSWORD)) quit(1);
if (!d.accidents.getIndexes().some(i => i.key.location === '2dsphere')) quit(2);
const info = d.getCollectionInfos({name:'accidents'})[0];
if (!info.options.validator.$jsonSchema.required.includes('location')) quit(3);
print('PASS: MongoDB application authentication, GeoJSON validator, 2dsphere index');
'''
    print(compose('exec', '-T', 'mongodb', 'mongosh', '--quiet', '--eval', mongo))

    dask = '''
from distributed import Client
def cache_is_writable():
    import os
    return os.access('/data', os.W_OK)
with Client('tcp://dask-scheduler:8786', timeout='10s') as c:
    c.wait_for_workers(2, timeout=20)
    workers = c.scheduler_info()['workers']
    assert {w['name'] for w in workers.values()} == {'worker-1', 'worker-2'}
    futures = [c.submit(sum, [1, 2, 3], workers=[address], allow_other_workers=False, pure=False) for address in workers]
    assert c.gather(futures) == [6, 6]
    assert all(c.run(cache_is_writable).values()), 'Dataset cache must be writable by both workers'
    print('PASS: Dask executed a task on each of two registered workers')
    print('PASS: dataset cache is writable by both workers')
'''
    print(compose('exec', '-T', 'dask-scheduler', 'python', '-c', dask))
    spark = '''
import json
from urllib.request import urlopen
with urlopen('http://spark-master:8080/json/', timeout=5) as r:
    info = json.load(r)
assert len([w for w in info['workers'] if w['state'] == 'ALIVE']) >= 1
print('PASS: Spark master has an ALIVE worker')
'''
    print(compose('exec', '-T', 'spark-master', 'python3', '-c', spark))
    output = compose('exec', '-T', 'spark-master', '/opt/spark/bin/spark-submit', '/opt/smoke_spark.py')
    assert 'PASS:' in output
    print(output)
    print(compose('exec', '-T', 'jenkins', 'docker', 'version', '--format', 'Docker server: {{.Server.Version}}'))
    print(compose('exec', '-T', 'jenkins', 'docker', 'compose', 'version'))
    print('Infrastructure verification completed. No dataset downloaded or processed.')


if __name__ == '__main__':
    main()

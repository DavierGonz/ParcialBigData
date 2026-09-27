"""Versioned Kaggle REST API cache. Credentials exist only in process memory."""
import base64
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile
from contextlib import contextmanager

DATASET = 'sobhanmoosavi/us-accidents'
API = 'https://www.kaggle.com/api/v1/datasets'


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if result is not None:
            result.remove_header('Authorization')
        return result


def authorization(value):
    value = value.strip()
    if not value:
        raise ValueError('Missing Kaggle credential')
    if value.startswith('{'):
        config = json.loads(value)
        pair = f"{config['username']}:{config['key']}"
        return 'Basic ' + base64.b64encode(pair.encode()).decode()
    return 'Bearer ' + value


def fetch(url):
    headers = {'User-Agent': 'ParcialBigData-academic-ingestion/1'}
    headers['Authorization'] = authorization(os.environ.get('KAGGLE_CREDENTIAL', ''))
    opener = urllib.request.build_opener(SafeRedirect())
    return opener.open(urllib.request.Request(url, headers=headers), timeout=120)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


@contextmanager
def cache_lock(root):
    # Container-only advisory lock is released even when a job is killed.
    import fcntl
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.ingestion.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def download(root, version=13, opener=fetch):
    start = time.monotonic()
    directory = Path(root) / f'us-accidents-v{version}'
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (manifest['version'] == version and all(
            (directory / item['name']).is_file()
            and sha256(directory / item['name']) == item['sha256']
            for item in manifest['artifacts']
        )):
            return manifest, {'cache_hit': True, 'downloaded_bytes': 0,
                              'seconds': time.monotonic() - start}
    with opener(f'{API}/view/{DATASET}') as response:
        metadata = json.load(response)
    if int(metadata['currentVersionNumber']) != version:
        raise ValueError('Dataset version changed: review and explicitly pin the new version')
    archive = directory / 'us-accidents.zip'
    temporary = directory / 'download.part'
    with opener(f'{API}/download/{DATASET}?datasetVersionNumber={version}') as response:
        expected = response.headers.get('Content-Length')
        with temporary.open('wb') as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    size = temporary.stat().st_size
    if expected and size != int(expected):
        raise ValueError('Incomplete Kaggle response')
    artifacts = []
    with zipfile.ZipFile(temporary) as zipped:
        members = [member for member in zipped.infolist() if not member.is_dir()]
        if len(members) != 1 or not members[0].filename.lower().endswith('.csv'):
            raise ValueError('Unexpected dataset archive schema; expected one CSV')
        member = members[0]
        if Path(member.filename).name != member.filename or '\\' in member.filename:
            raise ValueError('Unsafe archive filename')
        csv_path = directory / member.filename
        with zipped.open(member) as source, csv_path.with_suffix('.part').open('wb') as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
        csv_path.with_suffix('.part').replace(csv_path)
    temporary.replace(archive)
    for path in (archive, csv_path):
        artifacts.append({'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    with csv_path.open(newline='', encoding='utf-8') as stream:
        columns = next(csv.reader(stream))
    required = {'ID', 'Start_Lat', 'Start_Lng', 'Start_Time', 'Severity', 'State'}
    if not required.issubset(columns) or len(columns) != len(set(columns)):
        raise ValueError('Missing or duplicated CSV columns')
    manifest = {'dataset': DATASET, 'version': version, 'source_updated': metadata['lastUpdated'],
                'license': metadata['licenseName'], 'downloaded_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'source_bytes': metadata['totalBytes'], 'artifacts': artifacts,
                'csv': csv_path.name, 'columns': columns}
    atomic_json(manifest_path, manifest)
    return manifest, {'cache_hit': False, 'downloaded_bytes': size, 'seconds': time.monotonic() - start}

"""Fetch pinned connector and driver jars at build time, not per Spark job."""
from pathlib import Path
import hashlib
from urllib.request import urlopen

artifacts = [
    ('org/mongodb/spark', 'mongo-spark-connector_2.12', '10.7.0'),
    ('org/mongodb', 'mongodb-driver-sync', '5.1.4'),
    ('org/mongodb', 'mongodb-driver-core', '5.1.4'),
    ('org/mongodb', 'bson', '5.1.4'),
]
for group, artifact, version in artifacts:
    filename = f'{artifact}-{version}.jar'
    url = f'https://repo.maven.apache.org/maven2/{group}/{artifact}/{version}/{filename}'
    with urlopen(url, timeout=60) as response:
        data = response.read()
    with urlopen(url + '.sha1', timeout=60) as response:
        expected = response.read().decode().strip().split()[0]
    if hashlib.sha1(data).hexdigest() != expected:
        raise RuntimeError(f'Checksum mismatch: {filename}')
    Path('/opt/spark/jars', filename).write_bytes(data)

"""Health probe: verify scheduler RPC and, for workers, their registration."""
import sys
from distributed import Client

with Client('tcp://dask-scheduler:8786', timeout='5s', set_as_default=False) as client:
    workers = client.scheduler_info()['workers']
    if len(sys.argv) > 1:
        assert any(w['name'] == sys.argv[1] for w in workers.values()), 'Worker not registered'

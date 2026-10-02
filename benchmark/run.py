import argparse
import fcntl
import json
from pathlib import Path
import time

from benchmark.common import EXPECTED_ROWS, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['spark','dask'])
    parser.add_argument('--workers', type=int, choices=[1,2], required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path('/data/benchmark-v1')
    manifest = json.loads((root/'manifest.json').read_text())
    golden = json.loads((root/'golden.json').read_text())
    assert manifest['rows'] == EXPECTED_ROWS
    with open('/data/.ingestion.lock','r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        startup = time.perf_counter()
        if args.engine == 'spark':
            from pyspark.sql import SparkSession
            from processing.aggregates import prepare, aggregate
            spark = SparkSession.builder.appName('phase5-grid').getOrCreate()
            version = spark.version
            spark.sparkContext.setLogLevel('WARN')
            from urllib.request import urlopen
            with urlopen('http://bench-spark-master:8080/json/') as response:
                workers = [w for w in json.load(response)['workers'] if w['state']=='ALIVE']
            assert len(workers) == args.workers
            t0 = time.perf_counter()
            frames = [spark.read.option('header','true').schema('ID string, Start_Lng double, Start_Lat double, Start_Time string').csv(str(root/f['name'])) for f in manifest['files']]
            frame = frames[0]
            for part in frames[1:]: frame = frame.unionByName(part)
            partitions = frame.rdd.getNumPartitions()
            result = aggregate(prepare(frame), 'benchmark')['grid'].select('cell_x','cell_y','count').collect()
            rows = [(r.cell_x,r.cell_y,r['count']) for r in result]
            elapsed = time.perf_counter()-t0
            # Only the 23,599 aggregated cells are collected, never source rows.
            task_retries = None  # counted from Spark event logs by the host
            spark.stop()
        else:
            import dask.dataframe as dd
            import dask
            version = dask.__version__
            from distributed import Client, get_task_stream
            from benchmark.dask_grid import grid
            with Client('tcp://bench-dask-scheduler:8786') as client:
                client.wait_for_workers(args.workers, timeout=60)
                assert len(client.scheduler_info()['workers']) == args.workers
                t0 = time.perf_counter()
                with get_task_stream(client) as events:
                    frame = dd.read_csv([str(root/f['name']) for f in manifest['files']], blocksize=None,
                                        dtype={'ID':'object','Start_Lng':'float64','Start_Lat':'float64','Start_Time':'object'}, float_precision='round_trip')
                    partitions = frame.npartitions
                    result = grid(frame).compute(retries=0)
                rows = list(result[['cell_x','cell_y','count']].itertuples(index=False,name=None))
                elapsed = time.perf_counter()-t0
                task_retries = sum(e.get('status') != 'OK' for e in events.data)
                keys = [str(e['key']) for e in events.data]
                telemetry = {'task_retries':len(keys)-len(set(keys)),
                             'workers_used':len({e['worker'] for e in events.data})}
        assert partitions == 8
        proof = verify(rows, golden)
        assert proof['sum_counts'] == EXPECTED_ROWS
        report = {'engine':args.engine,'version':version,'workers':args.workers,'operation_seconds':elapsed,
                  'application_seconds':time.perf_counter()-startup,'input_partitions':partitions,
                  'records_processed':proof['sum_counts'],'errors':0,'failed_task_events':task_retries,**proof}
        if args.engine == 'dask': report.update(telemetry)
        Path(args.output).write_text(json.dumps(report,indent=2))
        print(json.dumps(report))


if __name__ == '__main__': main()

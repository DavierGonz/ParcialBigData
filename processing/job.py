"""Spark SQL analytics. Only bounded scalar results return to the driver."""
import argparse
import fcntl
import json
from pathlib import Path
import time

from pyspark import StorageLevel
from pyspark.sql import SparkSession, functions as F

from processing.aggregates import METHOD_VERSION, CELL_DEGREES, prepare, aggregate
from processing.storage import database, identity, configure_session, read_source, write_result, ensure_indexes, verify


def execute(force=False):
    start=time.monotonic()
    # Same kernel lock as Dask ingestion. A read descriptor can take flock(LOCK_EX).
    with Path('/data/.ingestion.lock').open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        db=database()
        spark=None
        try:
            sources=list(db.ingestion_runs.find({'status':'complete'},{'_id':1,'verification.stored':1}).limit(2))
            if len(sources)!=1:
                raise RuntimeError('Exactly one completed source sample is required; explicitly select before adding versions')
            fingerprint=sources[0]['_id']
            expected=sources[0]['verification']['stored']
            assert expected>=1_000_000
            assert db.accidents.count_documents({'dataset_fingerprint':fingerprint})==expected
            run_id=identity(fingerprint)
            previous=db.analytics_runs.find_one({'_id':run_id,'status':'complete'})
            if previous and not force:
                proof=verify(db,run_id,expected,previous['invalid_timestamps'])
                report={**previous,'cache_hit':True,'verification':proof}
            else:
                manifest=json.loads(Path('/data/us-accidents-v13/manifest.json').read_text())
                ensure_indexes(db)
                spark=configure_session(SparkSession.builder.appName('us-accidents-phase4')).getOrCreate()
                spark.sparkContext.setLogLevel('WARN')
                source=read_source(spark,'accidents',fingerprint)
                frame=prepare(source).persist(StorageLevel.DISK_ONLY)
                metrics=frame.agg(F.count('*').alias('rows'),F.sum(F.col('event_time').isNull().cast('long')).alias('invalid')).first()
                assert metrics.rows==expected, 'Connector did not read the complete sample'
                invalid=int(metrics.invalid or 0)
                assert invalid<expected, 'No valid timestamps'
                results=aggregate(frame,run_id)
                for name,result in results.items():
                    write_result(result,'analytics_'+name)
                frame.unpersist()
                proof=verify(db,run_id,expected,invalid)
                report={'_id':run_id,'run_id':run_id,'status':'complete','cache_hit':False,
                        'source_fingerprint':fingerprint,'source_rows':expected,
                        'dataset_version':manifest['version'],'source_csv_sha256':next(a['sha256'] for a in manifest['artifacts'] if a['name']==manifest['csv']),
                        'method_version':METHOD_VERSION,'cell_degrees':CELL_DEGREES,'time_basis':'source local civil time; no UTC conversion',
                        'invalid_timestamps':invalid,'read_partitions':source.rdd.getNumPartitions(),
                        'verification':proof}
            report['seconds']=time.monotonic()-start
            path=Path('/data/analytics-report.json')
            temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps(report,indent=2))
            temporary.replace(path)
            if not report['cache_hit']:
                db.analytics_runs.replace_one({'_id':run_id},report,upsert=True)
            # Publish only after verification and durable report creation both succeed.
            db.analytics_state.replace_one({'_id':'active'},{'_id':'active','run_id':run_id},upsert=True)
            print(json.dumps(report),flush=True)
        finally:
            if spark is not None:
                spark.stop()
            db.client.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--force',action='store_true')
    execute(parser.parse_args().force)

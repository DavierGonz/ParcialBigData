"""Run the ingestion without changing the Flask deployment."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import dask.dataframe as dd
from distributed import Client

from ingestion.download import atomic_json, cache_lock, download
from ingestion.etl import ETL_VERSION, SAMPLE_SEED, database, process_partition, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='/data')
    parser.add_argument('--force-etl', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    start = time.monotonic()
    with cache_lock(args.root):
        manifest, transfer = download(args.root)
        csv_hash = next(item['sha256'] for item in manifest['artifacts'] if item['name'] == manifest['csv'])
        fingerprint = hashlib.sha256(json.dumps({'csv_sha256': csv_hash, 'version': manifest['version'], 'etl': ETL_VERSION, 'seed': SAMPLE_SEED, 'modulus': 7}, sort_keys=True).encode()).hexdigest()
        db = database()
        try:
            previous = db.ingestion_runs.find_one({'_id': fingerprint, 'status': 'complete'})
            if args.verify_only or (previous and not args.force_etl):
                proof = verify(db, fingerprint)
                if previous:
                    assert proof['stored'] == previous['verification']['stored'], 'Cached ETL count mismatch; run --force-etl'
                report = {'etl_cache_hit': True, 'download': transfer, 'verification': proof, 'fingerprint': fingerprint}
            else:
                db.accidents.create_index([('location', '2dsphere')], name='location_2dsphere')
                csv_path = Path(args.root) / 'us-accidents-v13' / manifest['csv']
                frame = dd.read_csv(str(csv_path), blocksize='16MiB', dtype=str, keep_default_na=False)
                partitions = frame.to_delayed()
                report = {'etl_cache_hit': False, 'download': transfer, 'manifest': manifest,
                          'fingerprint': fingerprint, 'etl_version': ETL_VERSION, 'seed': SAMPLE_SEED,
                          'sample_modulus': 7, 'partitions': [], 'partition_count': len(partitions)}
                db.ingestion_runs.update_one({'_id': fingerprint}, {'$set': {'status': 'running', 'etl_version': ETL_VERSION}}, upsert=True)
                etl_start = time.monotonic()
                with Client('tcp://dask-scheduler:8786') as client:
                    client.wait_for_workers(2, timeout=60)
                    # At most two CSV partitions are in flight. Data never returns to the driver.
                    from dask import delayed
                    for offset in range(0, len(partitions), 2):
                        tasks = [delayed(process_partition)(part, fingerprint) for part in partitions[offset:offset + 2]]
                        futures = client.compute(tasks, retries=1)
                        stats = client.gather(futures)
                        report['partitions'].extend(stats)
                        for future in futures:
                            future.release()
                        print(json.dumps({'completed_partitions': len(report['partitions']), 'total_partitions': len(partitions)}), flush=True)
                report['etl_seconds'] = time.monotonic() - etl_start
                keys = ('read', 'missing_coordinates', 'invalid_coordinates', 'out_of_range', 'missing_id', 'clean', 'selected', 'inserted', 'matched', 'modified')
                report['counts'] = {key: sum(item[key] for item in report['partitions']) for key in keys}
                report['verification'] = verify(db, fingerprint)
                report['duplicate_selected_rows'] = report['counts']['selected'] - report['verification']['stored']
                db.ingestion_runs.update_one({'_id': fingerprint}, {'$set': {'status': 'complete', 'verification': report['verification'], 'counts': report['counts']}})
            report['total_seconds'] = time.monotonic() - start
            atomic_json(Path(args.root) / 'last-ingestion-report.json', report)
            print(json.dumps({key: value for key, value in report.items() if key not in ('manifest', 'partitions')}, default=str), flush=True)
        finally:
            db.client.close()


if __name__ == '__main__':
    main()

"""Bounded partition tasks: clean, sample, transform and upsert on Dask workers."""
import hashlib
import os
import time

import numpy as np
import pandas as pd
from pymongo import MongoClient, ReplaceOne

ETL_VERSION = 'phase3-v1'
SAMPLE_SEED = 'us-accidents-academic-v1'


def database():
    name = os.environ.get('MONGO_DATABASE', 'us_accidents')
    return MongoClient('mongodb', username=os.environ['MONGO_APP_USERNAME'],
                       password=os.environ['MONGO_APP_PASSWORD'], authSource=name,
                       serverSelectionTimeoutMS=15000)[name]


def clean(frame):
    lat_raw, lon_raw = frame['Start_Lat'], frame['Start_Lng']
    nulls = ['', 'nan', 'null', 'none', 'na', 'n/a']
    missing = lat_raw.isna() | lon_raw.isna() | lat_raw.str.strip().str.lower().isin(nulls) | lon_raw.str.strip().str.lower().isin(nulls)
    lat = pd.to_numeric(lat_raw, errors='coerce')
    lon = pd.to_numeric(lon_raw, errors='coerce')
    invalid = ~missing & (~np.isfinite(lat) | ~np.isfinite(lon))
    outside = ~missing & ~invalid & (~lat.between(-90, 90) | ~lon.between(-180, 180))
    bad_id = ~(missing | invalid | outside) & (frame['ID'].isna() | frame['ID'].str.strip().eq(''))
    keep = ~(missing | invalid | outside | bad_id)
    result = frame.loc[keep].copy()
    result['Start_Lat'] = lat[keep].astype(float)
    result['Start_Lng'] = lon[keep].astype(float)
    counts = {'read': len(frame), 'missing_coordinates': int(missing.sum()),
              'invalid_coordinates': int(invalid.sum()), 'out_of_range': int(outside.sum()),
              'missing_id': int(bad_id.sum()), 'clean': int(keep.sum())}
    return result, counts


def selected(identifier, modulus=7):
    digest = hashlib.blake2b(f'{SAMPLE_SEED}:{identifier}'.encode(), digest_size=8).digest()
    return int.from_bytes(digest, 'big') % modulus == 0


def document(row, fingerprint):
    # MongoDB stores _id first. Matching that BSON field order avoids no-op replacements.
    record = {'_id': str(row['ID'])}
    record.update({key: None if pd.isna(value) else value for key, value in row.items()})
    record['location'] = {'type': 'Point', 'coordinates': [float(record['Start_Lng']), float(record['Start_Lat'])]}
    record['dataset_fingerprint'] = fingerprint
    # Preserve civil timestamps and Timezone from the source; do not invent UTC.
    severity = pd.to_numeric(record.get('Severity'), errors='coerce')
    record['Severity'] = None if pd.isna(severity) else int(severity)
    return record


def write_batch(collection, records):
    if not records:
        return {'inserted': 0, 'matched': 0, 'modified': 0}
    result = collection.bulk_write([ReplaceOne({'_id': item['_id']}, item, upsert=True) for item in records], ordered=False)
    return {'inserted': result.upserted_count, 'matched': result.matched_count, 'modified': result.modified_count}


def process_partition(frame, fingerprint, modulus=7, collection_name='accidents'):
    from distributed import get_worker
    import psutil
    start = time.monotonic()
    frame, counts = clean(frame)
    frame = frame.loc[frame['ID'].map(lambda value: selected(value, modulus))]
    counts.update(selected=len(frame), inserted=0, matched=0, modified=0)
    db = database()
    try:
        batch = []
        for values in frame.itertuples(index=False, name=None):
            row = dict(zip(frame.columns, values))
            batch.append(document(row, fingerprint))
            if len(batch) == 500:
                for key, value in write_batch(db[collection_name], batch).items():
                    counts[key] += value
                batch.clear()
        for key, value in write_batch(db[collection_name], batch).items():
            counts[key] += value
    finally:
        db.client.close()
    counts.update(seconds=time.monotonic() - start, worker=get_worker().name,
                  rss_bytes=psutil.Process().memory_info().rss)
    return counts


def verify(db, fingerprint, minimum=1_000_000, collection_name='accidents'):
    collection = db[collection_name]
    indexes = collection.index_information()
    assert any(item['key'] == [('location', '2dsphere')] for item in indexes.values()), 'Missing 2dsphere index'
    count = collection.count_documents({'dataset_fingerprint': fingerprint})
    assert count >= minimum, f'Only {count} clean documents; required {minimum}'
    valid = {'dataset_fingerprint': fingerprint, 'location.type': 'Point',
             'location.coordinates': {'$type': 'array', '$size': 2},
             'location.coordinates.0': {'$type': 'number', '$gte': -180, '$lte': 180},
             'location.coordinates.1': {'$type': 'number', '$gte': -90, '$lte': 90}}
    assert collection.count_documents(valid) == count, 'Invalid geometries exist'
    example = collection.find_one({'dataset_fingerprint': fingerprint})
    assert example, 'Empty collection'
    point = example['location']
    near = list(collection.find({'location': {'$near': {'$geometry': point, '$maxDistance': 1000}}}, {'_id': 1}).limit(5))
    within = collection.count_documents({'location': {'$geoWithin': {'$centerSphere': [point['coordinates'], 1 / 6378.1]}}})
    assert near and within >= 1
    return {'stored': count, 'total_collection': collection.estimated_document_count(),
            'index': indexes, 'near_results': len(near), 'within_1km': within, 'example_geometry': point}

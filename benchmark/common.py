import hashlib
import json
import math

EXPECTED_ROWS = 1_103_657
FINGERPRINT = 'cfce18489c4df70fe59c6166b61e0aafcebbb098b71b164ca9f9ada842fd22cf'


def cell(lon, lat):
    if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError('Invalid source coordinate')
    return min(3599, math.floor((lon + 180) * 10)), min(1799, math.floor((lat + 90) * 10))


def canonical(rows):
    values = sorted((int(x), int(y), int(n)) for x, y, n in rows)
    if len({(x,y) for x,y,n in values}) != len(values) or any(n <= 0 for x,y,n in values):
        raise ValueError('Duplicate cells or invalid counts')
    return values


def digest(rows):
    return hashlib.sha256(json.dumps(canonical(rows), separators=(',', ':')).encode()).hexdigest()


def verify(rows, expected):
    values = canonical(rows)
    if values != canonical(expected):
        raise ValueError('Grid differs from reference: exact cell/count comparison failed')
    return {'cells': len(values), 'sum_counts': sum(n for x,y,n in values), 'grid_sha256': digest(values)}

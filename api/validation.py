"""Bounded public inputs; clients never supply MongoDB query documents."""
import math

from werkzeug.exceptions import BadRequest


def number(value, name, low, high, *, json_number=False):
    if isinstance(value, bool) or (json_number and not isinstance(value, (int, float))):
        raise BadRequest(f'{name} must be a number')
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        raise BadRequest(f'{name} must be a finite number') from None
    if not math.isfinite(value) or not low <= value <= high:
        raise BadRequest(f'{name} must be between {low} and {high}')
    return value


def integer(value, name, low, high):
    if isinstance(value, bool) or len(str(value)) > 6 or not str(value).isascii() or not str(value).isdigit():
        raise BadRequest(f'{name} must be an integer')
    value = int(value)
    if not low <= value <= high:
        raise BadRequest(f'{name} must be between {low} and {high}')
    return value


def arguments(args, allowed):
    if set(args) - set(allowed) or any(len(args.getlist(key)) != 1 for key in args):
        raise BadRequest('Unknown or repeated query parameter')


def proximity(args):
    arguments(args, ('lat', 'lon', 'radius_m', 'limit'))
    lat = number(args.get('lat'), 'lat', -90, 90)
    lon = number(args.get('lon'), 'lon', -180, 180)
    radius = number(args.get('radius_m'), 'radius_m', 1, 50000)
    limit = integer(args.get('limit', 20), 'limit', 1, 100)
    return {'type': 'Point', 'coordinates': [lon, lat]}, radius, limit


def orientation(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def intersects(a, b, c, d):
    eps = 1e-12
    def on_segment(p, q, r):
        return abs(orientation(p,q,r)) < eps and all(min(p[i],q[i])-eps <= r[i] <= max(p[i],q[i])+eps for i in (0,1))
    turns = orientation(a,b,c), orientation(a,b,d), orientation(c,d,a), orientation(c,d,b)
    return ((turns[0]*turns[1] < 0 and turns[2]*turns[3] < 0)
            or on_segment(a,b,c) or on_segment(a,b,d) or on_segment(c,d,a) or on_segment(c,d,b))


def polygon(body):
    if not isinstance(body, dict) or set(body) - {'geometry', 'limit'}:
        raise BadRequest('Expected geometry and optional limit')
    geometry = body.get('geometry')
    if not isinstance(geometry, dict) or set(geometry) != {'type', 'coordinates'} or geometry['type'] != 'Polygon':
        raise BadRequest('geometry must be a GeoJSON Polygon')
    rings = geometry['coordinates']
    if not isinstance(rings, list) or len(rings) != 1:
        raise BadRequest('Exactly one exterior ring is supported; holes are not supported')
    ring = rings[0]
    if not isinstance(ring, list) or not 4 <= len(ring) <= 101:
        raise BadRequest('Polygon requires 4 to 101 positions including closure')
    points = []
    for position in ring:
        if not isinstance(position, list) or len(position) != 2:
            raise BadRequest('Each position must contain longitude and latitude')
        points.append([number(position[0], 'longitude', -180, 180, json_number=True),
                       number(position[1], 'latitude', -90, 90, json_number=True)])
    if points[0] != points[-1] or len(set(map(tuple, points[:-1]))) != len(points)-1:
        raise BadRequest('Ring must be closed with distinct vertices')
    if any(max(p[i] for p in points)-min(p[i] for p in points) > 5 for i in (0,1)):
        raise BadRequest('Polygon bounding box must span at most 5 degrees per axis; no antimeridian crossing')
    if abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]))) < 1e-12:
        raise BadRequest('Polygon has zero area')
    size = len(points)-1
    for i in range(size):
        for j in range(i+1,size):
            if j == i+1 or (i == 0 and j == size-1):
                continue
            if intersects(points[i],points[i+1],points[j],points[j+1]):
                raise BadRequest('Polygon must not self-intersect or touch itself')
    return {'type':'Polygon','coordinates':[points]}, integer(body.get('limit',20), 'limit',1,100)

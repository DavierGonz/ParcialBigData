import json


def parse_stats(line):
    """Accept Docker's ANSI-decorated JSON stream without changing the payload."""
    return json.loads(line[line.index('{'):line.rindex('}')+1])


def mib(value):
    number = value.split()[0]
    for unit, factor in [('GiB',1024),('MiB',1),('KiB',1/1024),('B',1/1024**2)]:
        if number.endswith(unit): return float(number[:-len(unit)])*factor
    raise ValueError('Unknown Docker memory unit')

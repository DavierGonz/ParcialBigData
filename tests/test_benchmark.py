import pytest

from benchmark.common import canonical, cell, digest, verify
from benchmark.metrics import mib, parse_stats


@pytest.mark.parametrize('lon,lat,expected', [(-180,-90,(0,0)),(180,90,(3599,1799)),
    (0,0,(1800,900)),(-0.01,-0.01,(1799,899)),(0.01,0.01,(1800,900)),(-118.3,34,(617,1240))])
def test_grid_boundaries(lon, lat, expected):
    assert cell(lon,lat) == expected


@pytest.mark.parametrize('lon,lat', [(181,0),(0,91),(float('nan'),0),(0,float('inf'))])
def test_invalid_coordinates(lon,lat):
    with pytest.raises(ValueError): cell(lon,lat)


def test_comparison_checks_cells_not_only_sum():
    with pytest.raises(ValueError): verify([(1,2,10)],[(2,1,10)])
    with pytest.raises(ValueError): canonical([(1,2,1),(1,2,2)])
    assert digest([(1,2,3),(4,5,6)]) == digest([(4,5,6),(1,2,3)])
    assert verify([(1,2,3)],[(1,2,3)])['sum_counts'] == 3


def test_metrics_ansi_and_units():
    assert parse_stats('\x1b[H{"MemUsage":"1.5GiB / 2GiB"}\x1b[K\n')['MemUsage']=='1.5GiB / 2GiB'
    assert mib('1.5GiB / 2GiB') == 1536
    assert mib('1024KiB / 2GiB') == 1
    with pytest.raises(ValueError): mib('unknown')

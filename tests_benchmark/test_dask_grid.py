import dask.dataframe as dd
import pandas as pd

from benchmark.common import cell, verify
from benchmark.dask_grid import grid


def test_partitioned_dask_matches_known_boundaries():
    points = [(-180,-90),(180,90),(-0.01,-0.01),(0.01,0.01),(0.02,0.02),(-118.3,34)]
    frame = dd.from_pandas(pd.DataFrame(points,columns=['Start_Lng','Start_Lat']),npartitions=3)
    result = grid(frame).compute(scheduler='synchronous')
    expected = {}
    for lon,lat in points:
        key=cell(lon,lat); expected[key]=expected.get(key,0)+1
    verify(result.itertuples(index=False,name=None), [(x,y,n) for (x,y),n in expected.items()])

def grid(frame):
    import numpy as np
    cells = frame.assign(cell_x=np.minimum(3599, np.floor((frame.Start_Lng+180)*10)).astype('int32'),
                         cell_y=np.minimum(1799, np.floor((frame.Start_Lat+90)*10)).astype('int32'))
    return cells.groupby(['cell_x','cell_y']).size(split_out=4).rename('count').reset_index()

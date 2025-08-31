import xarray as xr
import numpy as np

ds = xr.open_dataset("Data\CODEC_amax_ERA5_1979_2017_coor_mask_GUM_RPS.nc")  # engine guessed

# Inspect contents
print(ds.dims)
print(list(ds.data_vars))     # e.g., ['RPS','gum_loc','gum_scale','lon','lat',...]

# Get return periods (either a coord or attribute)
rps = ds.get('rp', None)
if rps is None:
    # Some files store RP values as an attribute; fallback to a known list
    rps = [5,10,25,50,100,1000]
else:
    rps = rps.values

# Build a nearest-point selector for Isla Trinitaria
target = np.array([-2.23, -79.90])  # lat, lon
lats = ds['lat'].values
lons = ds['lon'].values
# crude great-circle approximation
idx = np.argmin((lats - target[0])**2 + (lons - target[1])**2)

# Extract return levels (assumes RPS has shape [n_rp, n_points])
R = ds['RPS'].values[:, idx]  # metres above MSL
for rp, val in zip(rps, R):
    print(f"RP {rp} yr: {val:.3f} m (above MSL) at idx {idx}")

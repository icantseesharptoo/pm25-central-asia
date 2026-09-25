"""Item 3: download ERA5 boundary layer height (BLH) for the three stations.

BLH is in the ERA5 single-levels dataset (not ERA5-Land). We download a small
box around each station, year by year, and keep the nearest grid point.

Setup (once):
  1. Register at https://cds.climate.copernicus.eu and accept the ERA5 licence.
  2. Put your key in ~/.cdsapirc:
         url: https://cds.climate.copernicus.eu/api
         key: <your-personal-access-token>
  3. pip install cdsapi xarray netcdf4

Run:  python download/era5_blh.py --start 2020 --end 2025
Output: data/era5_blh_<city>.csv  with columns  datetime (UTC), blh (m)
"""
import argparse
from pathlib import Path

import cdsapi
import pandas as pd
import xarray as xr

STATIONS = {  # lat, lon of the monitors (US diplomatic posts)
    "almaty": (43.2341, 76.9533),
    "bishkek": (42.8278, 74.5826),
    "tashkent": (41.3669, 69.2719),
}
OUT = Path(__file__).resolve().parents[1] / "data"


def fetch(city: str, lat: float, lon: float, year: int, client: cdsapi.Client) -> pd.DataFrame:
    target = OUT / f"_blh_{city}_{year}.nc"
    if not target.exists():
        client.retrieve("reanalysis-era5-single-levels", {
            "product_type": ["reanalysis"],
            "variable": ["boundary_layer_height"],
            "year": [str(year)],
            "month": [f"{m:02d}" for m in range(1, 13)],
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": [lat + 0.5, lon - 0.5, lat - 0.5, lon + 0.5],   # N, W, S, E
            "data_format": "netcdf",
        }, str(target))
    ds = xr.open_dataset(target)
    tname = "valid_time" if "valid_time" in ds.coords else "time"
    s = ds["blh"].sel(latitude=lat, longitude=lon, method="nearest").to_series()
    return s.rename("blh").rename_axis("datetime").reset_index().rename(columns={tname: "datetime"})


def main(start: int, end: int):
    OUT.mkdir(exist_ok=True)
    client = cdsapi.Client()
    for city, (lat, lon) in STATIONS.items():
        parts = [fetch(city, lat, lon, y, client) for y in range(start, end + 1)]
        pd.concat(parts).to_csv(OUT / f"era5_blh_{city}.csv", index=False)
        print("wrote", OUT / f"era5_blh_{city}.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2020)
    ap.add_argument("--end", type=int, default=2025)
    a = ap.parse_args()
    main(a.start, a.end)

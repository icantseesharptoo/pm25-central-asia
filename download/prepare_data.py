"""Build data/<city>_merged.csv from PM2.5 + ERA5-Land (+ optional BLH).

Inputs per city (all timestamps UTC unless you change --pm-tz):
  --pm      PM2.5 CSV with columns datetime, pm25   (or openaq_<city>_hourly.csv;
            several stations are combined into a city median per hour)
  --era5    ERA5-Land time-series CSV with valid_time, t2m, d2m, u10, v10
            (temperatures in kelvin, as delivered by the CDS)
  --blh     optional output of era5_blh.py

Example:
  python download/prepare_data.py --city almaty --pm data/openaq_almaty_hourly.csv \
         --era5 data/era5land_almaty.csv --blh data/era5_blh_almaty.csv
The merged file is written in UTC, so set source_tz = "UTC" in config.py.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data"


def rh_magnus(t_c, td_c):
    """Relative humidity (%) from temperature and dew point (degC), Magnus form."""
    a, b = 17.625, 243.04
    return 100 * np.exp(a * td_c / (b + td_c)) / np.exp(a * t_c / (b + t_c))


def main(city, pm_path, era5_path, blh_path, pm_tz):
    pm = pd.read_csv(pm_path)
    pm["datetime"] = pd.to_datetime(pm["datetime"], utc=False)
    if pm["datetime"].dt.tz is None:
        pm["datetime"] = pm["datetime"].dt.tz_localize(pm_tz)
    pm["datetime"] = pm["datetime"].dt.tz_convert("UTC").dt.floor("h")
    pm = pm[pm["pm25"].between(0, 1500)]
    pm = pm.groupby("datetime")["pm25"].median()              # city median across stations

    e = pd.read_csv(era5_path)
    tcol = "valid_time" if "valid_time" in e else "datetime"
    e["datetime"] = pd.to_datetime(e[tcol], utc=True)
    e = e.set_index("datetime")
    met = pd.DataFrame(index=e.index)
    t_c = e["t2m"] - 273.15 if e["t2m"].mean() > 200 else e["t2m"]
    td_c = e["d2m"] - 273.15 if e["d2m"].mean() > 200 else e["d2m"]
    met["temp_c"], met["rh"] = t_c, rh_magnus(t_c, td_c)
    met["wind"] = np.hypot(e["u10"], e["v10"])

    df = met.join(pm, how="inner")
    if blh_path:
        b = pd.read_csv(blh_path)
        b["datetime"] = pd.to_datetime(b["datetime"], utc=True)
        df = df.join(b.set_index("datetime")["blh"], how="left")
    df.index = df.index.tz_localize(None)
    df.rename_axis("datetime").to_csv(OUT / f"{city}_merged.csv")
    print("wrote", OUT / f"{city}_merged.csv", len(df), "rows")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--pm", required=True)
    ap.add_argument("--era5", required=True)
    ap.add_argument("--blh")
    ap.add_argument("--pm-tz", default="UTC")
    a = ap.parse_args()
    main(a.city, a.pm, a.era5, a.blh, a.pm_tz)

"""Item 5: download hourly PM2.5 from every OpenAQ station in each city.

Uses the OpenAQ v3 API (free key: https://explore.openaq.org/register).
    export OPENAQ_API_KEY=...
    python download/openaq_stations.py --start 2020-01-01 --end 2025-12-31

Output:
    data/openaq_<city>_stations.csv   one row per station (id, name, provider, lat, lon)
    data/openaq_<city>_hourly.csv     datetime (UTC), sensor_id, location_id, pm25

Notes
  * OpenAQ timestamps are UTC. Keep source_tz = "UTC" in config.py for these files.
  * Low-cost sensors (e.g. PurpleAir, AirGradient) need humidity correction before
    they are mixed with reference monitors; the station list marks each provider.
"""
import argparse
import os
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://api.openaq.org/v3"
CITIES = {  # centre and search radius (m)
    "almaty": (43.2380, 76.9450, 25000),
    "bishkek": (42.8746, 74.5698, 20000),
    "tashkent": (41.2995, 69.2401, 25000),
}
PM25_PARAMETER_ID = 2
OUT = Path(__file__).resolve().parents[1] / "data"


def get(session, path, **params):
    for attempt in range(5):
        r = session.get(f"{API}{path}", params=params, timeout=60)
        if r.status_code == 429:                       # rate limited
            time.sleep(int(r.headers.get("x-ratelimit-reset", 30)) + 1)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Too many retries for {path}")


def stations(session, lat, lon, radius):
    js = get(session, "/locations", coordinates=f"{lat},{lon}", radius=radius,
             parameters_id=PM25_PARAMETER_ID, limit=1000)
    rows = []
    for loc in js["results"]:
        for s in loc["sensors"]:
            if s["parameter"]["id"] == PM25_PARAMETER_ID:
                rows.append({"location_id": loc["id"], "sensor_id": s["id"], "name": loc["name"],
                             "provider": (loc.get("provider") or {}).get("name"),
                             "is_monitor": loc.get("isMonitor"),
                             "lat": loc["coordinates"]["latitude"], "lon": loc["coordinates"]["longitude"]})
    return pd.DataFrame(rows)


def hourly(session, sensor_id, start, end):
    rows, page = [], 1
    while True:
        js = get(session, f"/sensors/{sensor_id}/hours", datetime_from=start, datetime_to=end,
                 limit=1000, page=page)
        res = js["results"]
        rows += [{"datetime": r["period"]["datetimeFrom"]["utc"], "pm25": r["value"]} for r in res]
        if len(res) < 1000:
            return pd.DataFrame(rows)
        page += 1


def main(start, end):
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        raise SystemExit("Set OPENAQ_API_KEY first.")
    OUT.mkdir(exist_ok=True)
    s = requests.Session()
    s.headers["X-API-Key"] = key
    for city, (lat, lon, radius) in CITIES.items():
        st = stations(s, lat, lon, radius)
        st.to_csv(OUT / f"openaq_{city}_stations.csv", index=False)
        print(f"{city}: {len(st)} PM2.5 sensors")
        parts = []
        for _, row in st.iterrows():
            df = hourly(s, row.sensor_id, start, end)
            if len(df):
                df["sensor_id"], df["location_id"] = row.sensor_id, row.location_id
                parts.append(df)
        if parts:
            pd.concat(parts).to_csv(OUT / f"openaq_{city}_hourly.csv", index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2025-12-31")
    a = ap.parse_args()
    main(a.start, a.end)

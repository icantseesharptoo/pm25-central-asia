"""Item 2: check whether timestamps are UTC or local time.

For each city we compute the mean diurnal cycle twice: once assuming the raw
timestamps are UTC and once assuming they are already local time. In
coal-heating cities the winter cycle normally shows a morning minimum around
dawn and an evening maximum after 19:00 local time. The assumption that
produces this shape is most likely correct; the table lets you decide.
"""
import pandas as pd

import config
from src.data import load_city


def diurnal_peaks(df: pd.DataFrame) -> dict:
    winter = df[df["heating"]]
    prof_all = df.groupby(df.index.hour)["pm25"].mean()
    prof_win = winter.groupby(winter.index.hour)["pm25"].mean()
    return {
        "peak_hour_all": int(prof_all.idxmax()),
        "min_hour_all": int(prof_all.idxmin()),
        "peak_hour_winter": int(prof_win.idxmax()),
        "min_hour_winter": int(prof_win.idxmin()),
    }


def run() -> pd.DataFrame:
    rows = []
    for city, cfg in config.CITIES.items():
        for label, src in [("raw = UTC", "UTC"), ("raw = local", cfg["local_tz"])]:
            df = load_city(city, source_tz_override=src)
            rows.append({"city": city, "assumption": label,
                         "configured": (cfg["source_tz"] or "") in (src,), **diurnal_peaks(df)})
    out = pd.DataFrame(rows)
    out.to_csv(config.RESULTS_DIR / "tz_check.csv", index=False)
    return out

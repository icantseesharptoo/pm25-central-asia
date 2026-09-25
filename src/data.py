"""Loading, time-zone handling and basic cleaning."""
import pandas as pd

import config


def load_city(name: str, source_tz_override: str | None = None) -> pd.DataFrame:
    """Load one city's hourly CSV, standardise columns, and index by local time.

    The returned frame has a tz-naive DatetimeIndex in local clock time, so that
    `index.hour` is the local hour of day.
    """
    cfg = config.CITIES[name]
    raw = pd.read_csv(cfg["file"])
    rename = {v: k for k, v in config.COLUMN_MAP.items() if v in raw.columns}
    df = raw.rename(columns=rename)[list(rename.values())]

    ts = pd.to_datetime(df.pop("datetime"), utc=False)
    src = source_tz_override or cfg["source_tz"] or cfg["local_tz"]
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(src, ambiguous="NaT", nonexistent="NaT")
    ts = ts.dt.tz_convert(cfg["local_tz"]).dt.tz_localize(None)

    df.index = ts
    df = df[~df.index.isna()].sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df = df.loc[config.STUDY_START:config.STUDY_END]
    df = df[df["pm25"].between(0, 1500)]          # drop impossible values
    df["heating"] = df.index.month.isin(config.HEATING_MONTHS)
    return df


def completeness(df: pd.DataFrame) -> float:
    """Share of hours in the study period that have a PM2.5 value."""
    full = pd.date_range(config.STUDY_START, config.STUDY_END, freq="h")
    return df["pm25"].reindex(full).notna().mean()

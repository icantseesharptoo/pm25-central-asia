import argparse
import os
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests


API = "https://api.openaq.org/v3"

CITIES = {
    "almaty": (43.2380, 76.9450, 25000),
    "bishkek": (42.8746, 74.5698, 20000),
    "tashkent": (41.2995, 69.2401, 25000),
}

PM25_PARAMETER_ID = 2

OUT = Path(__file__).resolve().parents[1] / "data"


def get(session, path, **params):
    for attempt in range(5):
        try:
            r = session.get(
                f"{API}{path}",
                params=params,
                timeout=120,
            )

            if r.status_code == 429:
                wait = int(
                    r.headers.get(
                        "x-ratelimit-reset",
                        30
                    )
                ) + 1

                print(f"Rate limit. Waiting {wait} seconds...")
                time.sleep(wait)
                continue

            if r.status_code == 408:
                print(
                    f"408 timeout. "
                    f"Retry {attempt + 1}/5..."
                )
                time.sleep(10 * (attempt + 1))
                continue

            r.raise_for_status()

            return r.json()

        except requests.RequestException as e:
            if attempt == 4:
                raise

            print(
                f"Request error: {e}. "
                f"Retrying..."
            )

            time.sleep(10 * (attempt + 1))

    raise RuntimeError(
        f"Too many retries for {path}"
    )


def stations(session, lat, lon, radius):
    js = get(
        session,
        "/locations",
        coordinates=f"{lat},{lon}",
        radius=radius,
        parameters_id=PM25_PARAMETER_ID,
        limit=1000,
    )

    rows = []

    for loc in js["results"]:
        for sensor in loc["sensors"]:

            if sensor["parameter"]["id"] != PM25_PARAMETER_ID:
                continue

            rows.append(
                {
                    "location_id": loc["id"],
                    "sensor_id": sensor["id"],
                    "name": loc["name"],
                    "provider": (
                        loc.get("provider") or {}
                    ).get("name"),
                    "is_monitor": loc.get(
                        "isMonitor"
                    ),
                    "lat": loc["coordinates"][
                        "latitude"
                    ],
                    "lon": loc["coordinates"][
                        "longitude"
                    ],
                }
            )

    return pd.DataFrame(rows)


def hourly_range(
    session,
    sensor_id,
    start_dt,
    end_dt,
):
    """
    Download one relatively short time range.
    """

    rows = []
    page = 1

    start_string = start_dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    end_string = end_dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    while True:
        js = get(
            session,
            f"/sensors/{sensor_id}/hours",
            datetime_from=start_string,
            datetime_to=end_string,
            limit=1000,
            page=page,
        )

        res = js["results"]

        for r in res:
            rows.append(
                {
                    "datetime": r["period"][
                        "datetimeFrom"
                    ]["utc"],
                    "pm25": r["value"],
                }
            )

        if len(res) < 1000:
            break

        page += 1

    return pd.DataFrame(rows)


def hourly(
    session,
    sensor_id,
    start_dt,
    end_dt,
):
    """
    Download data month by month.
    """

    parts = []

    current = start_dt

    while current <= end_dt:

        next_month = (
            current + timedelta(days=32)
        ).replace(day=1)

        chunk_end = min(
            next_month - timedelta(seconds=1),
            end_dt,
        )

        df = hourly_range(
            session,
            sensor_id,
            current,
            chunk_end,
        )

        if len(df):
            parts.append(df)

        current = next_month

    if not parts:
        return pd.DataFrame(
            columns=["datetime", "pm25"]
        )

    result = pd.concat(
        parts,
        ignore_index=True,
    )

    return result


def parse_start(value):
    return datetime.strptime(
        value,
        "%Y-%m-%d",
    ).replace(
        hour=0,
        minute=0,
        second=0,
        tzinfo=timezone.utc,
    )


def parse_end(value):
    return datetime.strptime(
        value,
        "%Y-%m-%d",
    ).replace(
        hour=23,
        minute=59,
        second=59,
        tzinfo=timezone.utc,
    )


def main(start, end):

    key = os.environ.get(
        "OPENAQ_API_KEY"
    )

    if not key:
        raise SystemExit(
            "Set OPENAQ_API_KEY first."
        )

    start_dt = parse_start(start)
    end_dt = parse_end(end)

    OUT.mkdir(exist_ok=True)

    session = requests.Session()

    session.headers[
        "X-API-Key"
    ] = key

    for city, (lat, lon, radius) in CITIES.items():

        print(f"\n=== {city.upper()} ===")

        st = stations(
            session,
            lat,
            lon,
            radius,
        )

        st_file = OUT / (
            f"openaq_{city}_stations.csv"
        )

        st.to_csv(
            st_file,
            index=False,
        )

        print(
            f"{city}: "
            f"{len(st)} PM2.5 sensors"
        )

        parts = []

        for i, row in st.iterrows():

            print(
                f"[{i + 1}/{len(st)}] "
                f"sensor {row.sensor_id}"
            )

            try:
                df = hourly(
                    session,
                    int(row.sensor_id),
                    start_dt,
                    end_dt,
                )

            except Exception as e:
                print(
                    f"Skipping sensor "
                    f"{row.sensor_id}: {e}"
                )
                continue

            if len(df) == 0:
                continue

            df["sensor_id"] = (
                row.sensor_id
            )

            df["location_id"] = (
                row.location_id
            )

            parts.append(df)

        if not parts:
            print(
                f"No PM2.5 data for "
                f"{city}"
            )
            continue

        result = pd.concat(
            parts,
            ignore_index=True,
        )

        # Convert explicitly to UTC
        result["datetime"] = (
            pd.to_datetime(
                result["datetime"],
                utc=True,
                errors="coerce",
            )
        )

        # IMPORTANT:
        # remove anything outside requested range
        result = result[
            result["datetime"].between(
                pd.Timestamp(start_dt),
                pd.Timestamp(end_dt),
            )
        ]

        result = result.dropna(
            subset=["datetime", "pm25"]
        )

        result = result.sort_values(
            "datetime"
        )

        output = OUT / (
            f"openaq_{city}_hourly.csv"
        )

        result.to_csv(
            output,
            index=False,
        )

        print(
            f"\nWrote {output}"
        )

        print(
            "Rows:",
            len(result),
        )

        if len(result):
            print(
                "Period:",
                result["datetime"].min(),
                "->",
                result["datetime"].max(),
            )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start",
        default="2020-01-01",
    )

    parser.add_argument(
        "--end",
        default="2020-12-31",
    )

    args = parser.parse_args()

    main(
        args.start,
        args.end,
    )
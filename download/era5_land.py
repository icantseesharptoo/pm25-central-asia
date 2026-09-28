import argparse
import zipfile
from pathlib import Path

import cdsapi
import pandas as pd


STATIONS = {
    "almaty": (43.2341, 76.9533),
    "bishkek": (42.8278, 74.5826),
    "tashkent": (41.3669, 69.2719),
}

OUT = Path(__file__).resolve().parents[1] / "data"


def read_downloaded_file(path: Path) -> pd.DataFrame:
    """
    Reads ERA5-Land file returned by CDS.

    CDS may return:
    - normal CSV
    - ZIP archive containing several CSV files
      (for example wind and temperature separately)

    All CSV files are merged by valid_time.
    """

    if zipfile.is_zipfile(path):
        print("Downloaded file is ZIP archive")

        with zipfile.ZipFile(path, "r") as z:
            names = z.namelist()

            print("Files in archive:")
            for name in names:
                print("  ", name)

            csv_files = [
                name for name in names
                if name.lower().endswith(".csv")
            ]

            if not csv_files:
                raise RuntimeError(
                    f"No CSV found inside {path}. "
                    f"Archive contains: {names}"
                )

            frames = []

            for csv_name in csv_files:
                print("\nReading:", csv_name)

                with z.open(csv_name) as f:
                    df = pd.read_csv(f)

                print("Columns:", df.columns.tolist())

                if "valid_time" not in df.columns:
                    print(
                        f"Skipping {csv_name}: "
                        "no valid_time column"
                    )
                    continue

                # Remove location columns before merging
                # so we don't create latitude_x / latitude_y etc.
                drop_cols = [
                    c for c in ["latitude", "longitude"]
                    if c in df.columns
                ]

                df = df.drop(columns=drop_cols)

                frames.append(df)

            if not frames:
                raise RuntimeError(
                    "No usable CSV files found in ERA5-Land archive."
                )

            # Start with the first CSV
            result = frames[0]

            # Merge all remaining CSV files by time
            for frame in frames[1:]:
                result = pd.merge(
                    result,
                    frame,
                    on="valid_time",
                    how="outer",
                )

            return result

    print("Downloaded file is normal CSV")
    return pd.read_csv(path)

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    print("\nColumns received from CDS:")
    print(df.columns.tolist())

    rename_map = {
        # Time
        "time": "valid_time",
        "date": "valid_time",
        "datetime": "valid_time",
        "valid_time": "valid_time",

        # Temperature
        "2m_temperature": "t2m",
        "t2m": "t2m",

        # Dewpoint
        "2m_dewpoint_temperature": "d2m",
        "d2m": "d2m",

        # Wind
        "10m_u_component_of_wind": "u10",
        "u10": "u10",

        "10m_v_component_of_wind": "v10",
        "v10": "v10",
    }

    df = df.rename(columns=rename_map)

    required = [
        "valid_time",
        "t2m",
        "d2m",
        "u10",
        "v10",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        print("\nERROR: required columns are missing:")
        print(missing)

        print("\nActual columns:")
        print(df.columns.tolist())

        raise RuntimeError(
            "ERA5-Land CSV does not contain all required columns."
        )

    df = df[required].copy()

    df["valid_time"] = pd.to_datetime(
        df["valid_time"],
        errors="coerce"
    )

    df = df.dropna(subset=["valid_time"])

    df = (
        df
        .sort_values("valid_time")
        .drop_duplicates("valid_time")
        .reset_index(drop=True)
    )

    return df


def download_city(
    city: str,
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    client: cdsapi.Client,
):
    print(f"\n=== {city.upper()} ===")

    temp_file = OUT / f"_era5land_{city}.csv"
    output_file = OUT / f"era5land_{city}.csv"

    request = {
        "variable": [
            "2m_temperature",
            "2m_dewpoint_temperature",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
        ],

        "location": {
            "longitude": lon,
            "latitude": lat,
        },

        "date": [
            f"{start_year}-01-01",
            f"{end_year}-12-31",
        ],

        "data_format": "csv",
    }

    if not temp_file.exists():
        print(
            f"Downloading ERA5-Land for {city}: "
            f"{start_year}-{end_year}"
        )

        client.retrieve(
            "reanalysis-era5-land-timeseries",
            request,
            str(temp_file),
        )

    else:
        print("Using existing downloaded file:")
        print(temp_file)

    df = read_downloaded_file(temp_file)

    df = standardize_columns(df)

    df.to_csv(
        output_file,
        index=False
    )

    print("\nCreated:")
    print(output_file)

    print("Rows:", len(df))

    print("Period:")
    print(df["valid_time"].min(), "->", df["valid_time"].max())


def main(start: int, end: int):
    OUT.mkdir(exist_ok=True)

    client = cdsapi.Client()

    for city, (lat, lon) in STATIONS.items():
        download_city(
            city=city,
            lat=lat,
            lon=lon,
            start_year=start,
            end_year=end,
            client=client,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start",
        type=int,
        default=2020,
        help="Start year",
    )

    parser.add_argument(
        "--end",
        type=int,
        default=2020,
        help="End year",
    )

    args = parser.parse_args()

    main(
        start=args.start,
        end=args.end,
    )
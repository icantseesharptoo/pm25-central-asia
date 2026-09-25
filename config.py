"""Settings for the PM2.5 regimes pipeline. Edit this file to point at your data.

Each city needs one hourly CSV. Map your own column names to the standard names
used by the pipeline in COLUMN_MAP. Only `datetime` and `pm25` are required;
the meteorological columns are used when present.
"""
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"

# One entry per city.
#   file:      hourly CSV (merged PM2.5 + meteorology)
#   source_tz: time zone the timestamps are stored in. OpenAQ exports are UTC;
#              AirNow/StateAir files are usually local time. Use "UTC" or an IANA
#              zone. Set to None if you are unsure: the pipeline will then report
#              the diurnal peak under both assumptions (see results/tz_check.csv).
#   local_tz:  IANA zone of the city. zoneinfo handles historical offset changes
#              (Almaty was UTC+6 until 1 March 2024 and UTC+5 afterwards).
CITIES = {
    "Almaty":   {"file": DATA_DIR / "almaty_merged.csv",   "source_tz": "UTC",          "local_tz": "Asia/Almaty"},
    "Bishkek":  {"file": DATA_DIR / "bishkek_merged.csv",  "source_tz": "Asia/Bishkek", "local_tz": "Asia/Bishkek"},
    "Tashkent": {"file": DATA_DIR / "tashkent_merged.csv", "source_tz": "UTC",          "local_tz": "Asia/Tashkent"},
}

# Your column name -> standard name. Leave out columns you do not have.
COLUMN_MAP = {
    "datetime": "datetime",   # timestamp
    "pm25": "pm25",           # PM2.5, ug/m3
    "temp_c": "temp_c",       # 2 m air temperature, degC
    "rh": "rh",               # relative humidity, %
    "wind": "wind",           # 10 m wind speed, m/s
    "blh": "blh",             # ERA5 boundary layer height, m (optional)
}

STUDY_START = "2020-04-09"
STUDY_END = "2022-04-30 23:00"

HEATING_MONTHS = [10, 11, 12, 1, 2, 3]   # October-March

# Forecasting experiment
HORIZON_H = 24          # predict PM2.5 this many hours ahead
TEST_FRACTION = 0.25    # last 25% of the common period is the test window
RANDOM_SEED = 42

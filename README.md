# PM2.5 regimes in Almaty, Bishkek and Tashkent

Code for the paper *Persistent, Episodic, or Background? An Open-Data Comparison
of PM2.5 Regimes in Almaty, Bishkek, and Tashkent*.

The pipeline merges hourly PM2.5 from OpenAQ / AirNow with ERA5-Land and ERA5
reanalysis, then:

1. checks whether timestamps are UTC or local time (`results/tz_check.csv`);
2. tests heating vs non-heating differences (Mann–Whitney on daily means);
3. computes Spearman correlations with autocorrelation-adjusted p-values,
   partial correlations controlling for month, and heating-season correlations,
   including ERA5 boundary layer height when available;
4. trains a LightGBM day-ahead model per city and tests every model on every city
   (cross-city transfer);
5. writes LaTeX tables and number macros to `results/`, which the paper reads
   with `\input`.

## Quick start

```bash
pip install -r requirements.txt

# 1. Get data (skip if you already have merged files)
export OPENAQ_API_KEY=...                       # free key from explore.openaq.org
python download/openaq_stations.py --start 2020-01-01 --end 2025-12-31
python download/era5_blh.py --start 2020 --end 2025   # needs ~/.cdsapirc
python download/prepare_data.py --city almaty --pm data/openaq_almaty_hourly.csv \
       --era5 data/era5land_almaty.csv --blh data/era5_blh_almaty.csv
# ...repeat for bishkek and tashkent

# 2. Check config.py (file names, column names, source time zone, study period)

# 3. Run everything
python run_all.py
```

Copy `results/` next to `main.tex` in Overleaf and recompile. Before the
first real run, `python run_all.py --placeholders` writes placeholder tables so
the paper still compiles.

## Station map

`maps/station_maps.py` draws Fig. 1. It expects Natural Earth 10m GeoJSON layers
(countries, roads, rivers, lakes, urban areas) and geoBoundaries ADM1/ADM2 files
for KAZ, KGZ and UZB in the working directory.

## Input format

One CSV per city in `data/`, hourly, with at least `datetime` and `pm25`.
Optional: `temp_c` (°C), `rh` (%), `wind` (m/s), `blh` (m). Use `COLUMN_MAP` in
`config.py` if your column names differ.

## Time zones

OpenAQ exports are in UTC; AirNow/StateAir files are usually local time.
Set `source_tz` per city in `config.py`. `results/tz_check.csv` shows the
diurnal peak and minimum hour under both assumptions, so you can confirm the
choice: in heating season, coal-heated cities normally have a minimum around
midday and a maximum in the evening, local time.

## Data sources

- OpenAQ, https://openaq.org (CC BY 4.0)
- US Department of State AirNow / StateAir monitors
- Copernicus Climate Change Service, ERA5 and ERA5-Land reanalysis
- Boundaries: geoBoundaries; map layers: Natural Earth

## Licence

Code: MIT. Data remain under their original licences.

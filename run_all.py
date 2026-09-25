"""Run every analysis and write LaTeX-ready results to results/.

Usage:
    python run_all.py                 # full run on data/*.csv
    python run_all.py --placeholders  # write placeholder tables so the paper compiles
"""
import argparse
import json
import warnings

import pandas as pd

import config
from src import data, forecast, latex, stats_tests, timezone_check


FEATURE_NAMES = {
    "pm_lag0": "current PM$_{2.5}$", "pm_mean24": "24-h mean PM$_{2.5}$", "pm_max24": "24-h max PM$_{2.5}$",
    "pm_std24": "24-h PM$_{2.5}$ variability", "temp_c_t": "temperature", "temp_c_now": "current temperature",
    "blh_t": "boundary layer height", "blh_now": "current boundary layer height", "wind_t": "wind speed",
    "wind_now": "current wind speed", "rh_t": "humidity", "rh_now": "current humidity", "hour_t": "hour of day",
    "dow_t": "day of week", "heating_t": "heating season", "month_sin": "season", "month_cos": "season",
}


def pretty_feature(name: str) -> str:
    if name in FEATURE_NAMES:
        return FEATURE_NAMES[name]
    if name.startswith("pm_lag"):
        return f"PM$_{{2.5}}$ {name[6:]} h earlier"
    return name.replace("_", " ")


def main(placeholders: bool):
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", message=".*eval_set.*")
    config.RESULTS_DIR.mkdir(exist_ok=True)
    if placeholders:
        latex.write("tab_tests.tex", latex.tests_table({}, {}, placeholder=True))
        latex.write("tab_forecast.tex", latex.forecast_table(None, placeholder=True))
        latex.write("numbers.tex", latex.numbers(None))
        print("Placeholder tables written to", config.RESULTS_DIR)
        return

    print("1/4  Time-zone check")
    tz = timezone_check.run()
    print(tz.to_string(index=False))

    frames = {c: data.load_city(c) for c in config.CITIES}
    comp = {c: data.completeness(df) for c, df in frames.items()}

    print("2/4  Significance tests and partial correlations")
    mw = {c: stats_tests.mann_whitney_heating(df) for c, df in frames.items()}
    corr = {c: stats_tests.correlations(df) for c, df in frames.items()}
    blh = {c: stats_tests.blh_summary(df) for c, df in frames.items()}
    pd.DataFrame(mw).T.to_csv(config.RESULTS_DIR / "mann_whitney.csv")
    pd.DataFrame([{"city": c, **r} for c, rows in corr.items() for r in rows]).to_csv(
        config.RESULTS_DIR / "correlations.csv", index=False)
    json.dump(blh, open(config.RESULTS_DIR / "blh_summary.json", "w"), indent=2, default=float)

    print("3/4  Forecasting and cross-city transfer")
    res, imp, cutoff = forecast.run(frames)
    print(res.to_string(index=False))

    print("4/4  Writing LaTeX")
    ratios = {}
    for te in config.CITIES:
        self_rmse = res[(res.train == te) & (res.test == te)].rmse.iloc[0]
        for tr in config.CITIES:
            if tr != te:
                ratios[(tr, te)] = res[(res.train == tr) & (res.test == te)].rmse.iloc[0] / self_rmse
    worst = max(ratios, key=ratios.get)
    vals = {
        "FcCutoff": cutoff.strftime("%-d %B %Y"),
        "FcHorizon": str(config.HORIZON_H),
        "PenaltyMean": f"{(sum(ratios.values()) / len(ratios) - 1) * 100:.0f}",
        "PenaltyMax": f"{(ratios[worst] - 1) * 100:.0f}",
        "PenaltyMaxPair": f"{worst[0]} model applied to {worst[1]}",
        "TzNote": "; ".join(f"{c}: {config.CITIES[c]['source_tz'] or 'unknown'}" for c in config.CITIES),
    }
    for c in config.CITIES:
        vals[f"SelfRtwo{c}"] = f"{res[(res.train == c) & (res.test == c)].r2.iloc[0]:.2f}"
        vals[f"TopFeat{c}"] = pretty_feature(imp[c].index[0])
        vals[f"Comp{c}"] = f"{comp[c] * 100:.0f}"
    latex.write("tab_tests.tex", latex.tests_table(mw, corr))
    latex.write("tab_forecast.tex", latex.forecast_table(res))
    latex.write("numbers.tex", latex.numbers(vals))
    print("Done. Copy the results/ folder next to main.tex and recompile.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--placeholders", action="store_true")
    main(ap.parse_args().placeholders)

"""Item 1: day-ahead forecasting and cross-city transfer.

For every city we train a LightGBM model that predicts PM2.5 HORIZON_H hours
ahead from recent PM2.5, calendar features, and meteorology at the target hour
(a "perfect prognosis" setting: observed/reanalysis meteorology stands in for a
weather forecast). Each model is then tested on the held-out final part of the
period for all three cities. If the regimes really differ, a model should do
worse on another city than on its own.

The target is log1p(PM2.5) to tame the heavy right tail; predictions are
transformed back before scoring.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import config

MET = ["temp_c", "rh", "wind", "blh"]


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    h = config.HORIZON_H
    full = df.asfreq("h")                    # regular hourly grid, gaps as NaN
    pm = full["pm25"]
    X = pd.DataFrame(index=full.index)
    for lag in [0, 1, 2, 3, 6, 12, 24, 48]:
        X[f"pm_lag{lag}"] = pm.shift(lag)
    X["pm_mean24"] = pm.rolling(24, min_periods=18).mean()
    X["pm_max24"] = pm.rolling(24, min_periods=18).max()
    X["pm_std24"] = pm.rolling(24, min_periods=18).std()
    tgt_time = full.index + pd.Timedelta(hours=h)
    X["hour_t"] = tgt_time.hour
    X["dow_t"] = tgt_time.dayofweek
    X["month_sin"] = np.sin(2 * np.pi * tgt_time.month / 12)
    X["month_cos"] = np.cos(2 * np.pi * tgt_time.month / 12)
    X["heating_t"] = tgt_time.month.isin(config.HEATING_MONTHS).astype(int)
    for v in MET:
        if v in full:
            X[f"{v}_t"] = full[v].shift(-h)          # meteorology at target hour
            X[f"{v}_now"] = full[v]
    X["target"] = pm.shift(-h)
    X["persistence"] = pm                               # naive baseline
    return X.dropna(subset=["target", "pm_lag0", "pm_lag24"])


def split(X: pd.DataFrame, cutoff: pd.Timestamp):
    return X[X.index < cutoff], X[X.index >= cutoff]


def scores(y, yhat) -> dict:
    return {"rmse": float(np.sqrt(mean_squared_error(y, yhat))),
            "mae": float(mean_absolute_error(y, yhat)),
            "r2": float(r2_score(y, yhat))}


def run(frames: dict[str, pd.DataFrame]):
    feats = {c: make_features(df) for c, df in frames.items()}
    common = sorted(set.intersection(*[set(f.columns) for f in feats.values()]))
    cols = [c for c in common if c not in ("target", "persistence")]
    start = max(f.index.min() for f in feats.values())
    end = min(f.index.max() for f in feats.values())
    cutoff = start + (end - start) * (1 - config.TEST_FRACTION)

    params = dict(objective="regression", learning_rate=0.03, num_leaves=31,
                  min_child_samples=40, subsample=0.8, subsample_freq=1,
                  colsample_bytree=0.8, n_estimators=2000, verbose=-1,
                  random_state=config.RANDOM_SEED)
    models, rows, importance = {}, [], {}
    for train_city, X in feats.items():
        tr, _ = split(X, cutoff)
        n_val = int(len(tr) * 0.15)                         # last 15% of train for early stopping
        fit, val = tr.iloc[:-n_val], tr.iloc[-n_val:]
        m = lgb.LGBMRegressor(**params)
        m.fit(fit[cols], np.log1p(fit["target"]),
              eval_set=[(val[cols], np.log1p(val["target"]))],
              callbacks=[lgb.early_stopping(100, verbose=False)])
        models[train_city] = m
        gain = pd.Series(m.booster_.feature_importance("gain"), index=cols)
        importance[train_city] = (gain / gain.sum()).sort_values(ascending=False)

    for test_city, X in feats.items():
        _, te = split(X, cutoff)
        base = scores(te["target"], te["persistence"])
        rows.append({"train": "persistence", "test": test_city, **base})
        for train_city, m in models.items():
            yhat = np.expm1(m.predict(te[cols]))
            s = scores(te["target"], yhat)
            s["skill"] = 1 - s["rmse"] / base["rmse"]        # vs persistence
            rows.append({"train": train_city, "test": test_city, **s})
    res = pd.DataFrame(rows)
    res.to_csv(config.RESULTS_DIR / "forecast_transfer.csv", index=False)
    pd.DataFrame(importance).to_csv(config.RESULTS_DIR / "feature_importance.csv")
    return res, importance, cutoff

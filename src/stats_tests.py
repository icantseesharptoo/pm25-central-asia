"""Items 3 and 4: significance tests, partial correlations, boundary layer height.

Hourly PM2.5 is strongly autocorrelated, so ordinary p-values would be far too
small. We therefore
  * run the Mann-Whitney test on DAILY means (one value per day), and
  * compute p-values for hourly Spearman correlations with an effective sample
    size n_eff = n (1 - r1 s1) / (1 + r1 s1), where r1 and s1 are the lag-1
    autocorrelations of the two ranked series (Bretherton et al., 1999).
The seasonal cycle is removed with partial Spearman correlations: ranks of both
variables are regressed on month-of-year dummies and the residuals correlated.
"""
import numpy as np
import pandas as pd
from scipy import stats

import config

MET_VARS = [("temp_c", "T"), ("wind", "W"), ("rh", "RH"), ("blh", "BLH")]


def mann_whitney_heating(df: pd.DataFrame) -> dict:
    daily = df["pm25"].resample("D").mean().dropna()
    heat = daily[daily.index.month.isin(config.HEATING_MONTHS)]
    non = daily[~daily.index.month.isin(config.HEATING_MONTHS)]
    u, p = stats.mannwhitneyu(heat, non, alternative="greater")
    r_rb = 2 * u / (len(heat) * len(non)) - 1          # rank-biserial effect size
    return {"n_heat_days": len(heat), "n_non_days": len(non),
            "median_heat": heat.median(), "median_non": non.median(),
            "U": u, "p_mw": p, "r_rb": r_rb}


def _lag1(x: np.ndarray) -> float:
    return float(pd.Series(x).autocorr(lag=1))


def spearman_eff(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    """Spearman rho with an autocorrelation-adjusted p-value (hourly series)."""
    d = pd.concat([x, y], axis=1).dropna()
    rx, ry = d.iloc[:, 0].rank().values, d.iloc[:, 1].rank().values
    rho = stats.spearmanr(rx, ry).statistic
    n = len(d)
    a = _lag1(rx) * _lag1(ry)
    n_eff = max(int(n * (1 - a) / (1 + a)), 4)
    t = rho * np.sqrt((n_eff - 2) / max(1 - rho**2, 1e-12))
    p = 2 * stats.t.sf(abs(t), n_eff - 2)
    return rho, p, n_eff


def partial_spearman_month(df: pd.DataFrame, var: str) -> tuple[float, float, int]:
    """Spearman correlation of PM2.5 with `var`, controlling for month of year."""
    d = df[["pm25", var]].dropna()
    months = pd.get_dummies(d.index.month, drop_first=False).values.astype(float)
    res = []
    for col in ["pm25", var]:
        r = d[col].rank().values
        beta, *_ = np.linalg.lstsq(months, r, rcond=None)
        res.append(pd.Series(r - months @ beta, index=d.index))
    return spearman_eff(res[0], res[1])


def correlations(df: pd.DataFrame) -> list[dict]:
    rows = []
    for var, short in MET_VARS:
        if var not in df:
            continue
        rho, p, neff = spearman_eff(df["pm25"], df[var])
        prho, pp, pneff = partial_spearman_month(df, var)
        heat = df[df["heating"]]
        hrho, hp, hneff = spearman_eff(heat["pm25"], heat[var])
        rows.append({"var": short, "rho": rho, "p": p, "n_eff": neff,
                     "rho_partial": prho, "p_partial": pp,
                     "rho_heating": hrho, "p_heating": hp})
    return rows


def blh_summary(df: pd.DataFrame) -> dict:
    """How much of the winter excess coincides with a shallow boundary layer."""
    if "blh" not in df:
        return {}
    heat = df[df["heating"]].dropna(subset=["blh"])
    shallow = heat["blh"] <= heat["blh"].quantile(0.25)
    return {"blh_median_heat": heat["blh"].median(),
            "pm_shallow": heat.loc[shallow, "pm25"].mean(),
            "pm_deep": heat.loc[~shallow, "pm25"].mean()}

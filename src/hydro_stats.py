"""
Hydrological Statistics Module
================================
Flow duration curves, characteristic flows, and basic statistics.
"""

import pandas as pd
import numpy as np
from typing import Optional


def flow_duration_curve(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Compute flow duration curve (FDC) for a station.

    Returns DataFrame with columns: discharge, exceedance_pct
    Sorted from highest to lowest flow.
    """
    values = df.loc[df["station_id"] == station_id, column].dropna().values
    sorted_q = np.sort(values)[::-1]
    n = len(sorted_q)
    exceedance = np.arange(1, n + 1) / n * 100

    return pd.DataFrame({"discharge_m3s": sorted_q, "exceedance_pct": exceedance})


def characteristic_flows(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
) -> pd.Series:
    """Calculate characteristic flows for a station.

    Returns Series with: NNQ, SNQ, SSQ, SWQ, WWQ and percentile-based flows.
    Polish hydrological notation:
    - NNQ: absolute minimum (najnizszy z najnizszych)
    - SNQ: mean of annual minimums (sredni z najnizszych)
    - SSQ: mean flow (sredni ze srednich)
    - SWQ: mean of annual maximums (sredni z najwyzszych)
    - WWQ: absolute maximum (najwyzszy z najwyzszych)
    """
    sdf = df[df["station_id"] == station_id].copy()
    values = sdf[column].dropna()

    if values.empty:
        return pd.Series(dtype=float)

    # Annual stats
    sdf_valid = sdf.dropna(subset=[column, "date"])
    annual = sdf_valid.groupby(sdf_valid["date"].dt.year)[column]

    annual_min = annual.min()
    annual_max = annual.max()
    annual_mean = annual.mean()

    stats = pd.Series({
        "NNQ": values.min(),
        "SNQ": annual_min.mean(),
        "SSQ": values.mean(),
        "SWQ": annual_max.mean(),
        "WWQ": values.max(),
        "Q50": values.quantile(0.50),
        "Q90": values.quantile(0.10),   # Q90% exceedance = 10th percentile
        "Q95": values.quantile(0.05),   # Q95% exceedance = 5th percentile
        "Q_std": values.std(),
        "n_years": len(annual_mean),
        "n_observations": len(values),
    })
    return stats.round(4)


def monthly_stats(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Monthly mean, min, max discharge for a station.

    Returns DataFrame indexed by month (1-12) with mean, min, max, std.
    """
    sdf = df[df["station_id"] == station_id].dropna(subset=[column, "date"]).copy()
    sdf["month"] = sdf["date"].dt.month

    stats = sdf.groupby("month")[column].agg(["mean", "min", "max", "std", "count"])
    stats = stats.round(3)
    stats.index.name = "month"
    return stats


def annual_stats(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Annual mean, min, max discharge for a station."""
    sdf = df[df["station_id"] == station_id].dropna(subset=[column, "date"]).copy()
    sdf["year"] = sdf["date"].dt.year

    stats = sdf.groupby("year")[column].agg(["mean", "min", "max", "std", "count"])
    stats = stats.round(3)
    stats.index.name = "year"
    return stats

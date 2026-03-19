"""
Data Quality Module
====================
Check hydrological data for gaps, outliers, and fill missing values.
"""

import pandas as pd
import numpy as np
from typing import Optional


def check_completeness(df: pd.DataFrame, station_id: str) -> pd.DataFrame:
    """Check data completeness for a station. Returns summary by year.

    Args:
        df: DataFrame with 'date', 'station_id', 'discharge_m3s', 'water_level_cm'
        station_id: Station ID to check

    Returns:
        DataFrame with yearly completeness statistics
    """
    sdf = df[df["station_id"] == station_id].copy()
    if sdf.empty:
        return pd.DataFrame()

    sdf = sdf.set_index("date").sort_index()

    # Full date range
    date_range = pd.date_range(sdf.index.min(), sdf.index.max(), freq="D")
    sdf = sdf.reindex(date_range)

    # Stats by year
    yearly = sdf.groupby(sdf.index.year).agg(
        total_days=("discharge_m3s", "size"),
        discharge_valid=("discharge_m3s", lambda x: x.notna().sum()),
        discharge_missing=("discharge_m3s", lambda x: x.isna().sum()),
        level_valid=("water_level_cm", lambda x: x.notna().sum()),
        level_missing=("water_level_cm", lambda x: x.isna().sum()),
    )
    yearly["discharge_pct"] = (yearly["discharge_valid"] / yearly["total_days"] * 100).round(1)
    yearly["level_pct"] = (yearly["level_valid"] / yearly["total_days"] * 100).round(1)
    yearly.index.name = "year"
    return yearly


def find_gaps(df: pd.DataFrame, station_id: str, column: str = "discharge_m3s") -> pd.DataFrame:
    """Find gaps (missing data periods) in a station's time series.

    Returns DataFrame with gap start, end, and duration in days.
    """
    sdf = df[df["station_id"] == station_id][["date", column]].copy()
    sdf = sdf.sort_values("date").set_index("date")

    # Reindex to full range
    full_range = pd.date_range(sdf.index.min(), sdf.index.max(), freq="D")
    sdf = sdf.reindex(full_range)

    # Find consecutive NaN blocks
    is_missing = sdf[column].isna()
    groups = (is_missing != is_missing.shift()).cumsum()
    gaps = []
    for gid, group in sdf[is_missing].groupby(groups[is_missing]):
        gaps.append({
            "gap_start": group.index.min(),
            "gap_end": group.index.max(),
            "duration_days": len(group),
        })

    return pd.DataFrame(gaps) if gaps else pd.DataFrame(columns=["gap_start", "gap_end", "duration_days"])


def fill_gaps_interpolation(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
    max_gap_days: int = 5,
    method: str = "linear",
) -> pd.DataFrame:
    """Fill small gaps using interpolation.

    Only fills gaps up to max_gap_days long. Larger gaps are left as NaN.

    Args:
        df: Full DataFrame
        station_id: Station to process
        column: Column to interpolate
        max_gap_days: Maximum gap size to fill
        method: Interpolation method ('linear', 'spline', etc.)

    Returns:
        DataFrame with gaps filled for the given station
    """
    result = df.copy()
    mask = result["station_id"] == station_id
    sdf = result.loc[mask].sort_values("date").copy()

    sdf[column] = sdf[column].interpolate(method=method, limit=max_gap_days)
    result.loc[mask, column] = sdf[column].values
    return result


def fill_gaps_correlation(
    df: pd.DataFrame,
    target_id: str,
    reference_id: str,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Fill gaps using linear regression with a correlated reference station.

    Fits Q_target = a * Q_reference + b on overlapping valid data,
    then uses this to estimate missing values.

    Returns:
        DataFrame with gaps filled where reference data is available
    """
    result = df.copy()

    target = df[df["station_id"] == target_id][["date", column]].set_index("date")
    ref = df[df["station_id"] == reference_id][["date", column]].set_index("date")

    target.columns = ["target"]
    ref.columns = ["reference"]
    merged = target.join(ref, how="outer")

    # Fit on overlapping valid data
    valid = merged.dropna()
    if len(valid) < 30:
        print(f"Not enough overlapping data ({len(valid)} points). Need at least 30.")
        return result

    from scipy import stats
    slope, intercept, r_value, _, _ = stats.linregress(valid["reference"], valid["target"])
    print(f"Correlation R² = {r_value**2:.4f}, slope = {slope:.4f}, intercept = {intercept:.4f}")

    if r_value**2 < 0.7:
        print(f"Warning: weak correlation (R² = {r_value**2:.4f}). Results may be unreliable.")

    # Fill missing target using reference
    missing = merged["target"].isna() & merged["reference"].notna()
    filled_values = slope * merged.loc[missing, "reference"] + intercept

    # Apply to result
    mask = result["station_id"] == target_id
    sdf = result.loc[mask].set_index("date")
    sdf.loc[filled_values.index, column] = filled_values
    result.loc[mask, column] = sdf[column].values

    n_filled = missing.sum()
    print(f"Filled {n_filled} missing values using station {reference_id}")
    return result


def detect_outliers(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
    z_threshold: float = 4.0,
) -> pd.DataFrame:
    """Detect outliers using z-score on log-transformed data.

    Returns DataFrame of outlier rows.
    """
    sdf = df[df["station_id"] == station_id].copy()
    values = sdf[column].dropna()
    if values.empty:
        return pd.DataFrame()

    # Log transform (discharge is typically log-normal)
    log_values = np.log1p(values)
    z_scores = np.abs((log_values - log_values.mean()) / log_values.std())
    outlier_idx = z_scores[z_scores > z_threshold].index

    return sdf.loc[outlier_idx]



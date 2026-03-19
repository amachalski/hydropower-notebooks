"""
Hydrology Module
=================
Data quality, statistics, and flow interpolation for hydrological data.

Sections:
- Data quality: completeness, gaps, filling, outliers
- Statistics: FDC, characteristic flows, monthly/annual
- Flow interpolation: metoda interpolacyjna (drainage area ratio)
"""

import pandas as pd
import numpy as np
from typing import Optional


# ============================================================
# DATA QUALITY
# ============================================================

def check_completeness(df: pd.DataFrame, station_id: str) -> pd.DataFrame:
    """Check data completeness for a station. Returns summary by year."""
    sdf = df[df["station_id"] == station_id].copy()
    if sdf.empty:
        return pd.DataFrame()

    sdf = sdf.set_index("date").sort_index()
    date_range = pd.date_range(sdf.index.min(), sdf.index.max(), freq="D")
    sdf = sdf.reindex(date_range)

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

    full_range = pd.date_range(sdf.index.min(), sdf.index.max(), freq="D")
    sdf = sdf.reindex(full_range)

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
    """Fill small gaps using time-series interpolation.

    Only fills gaps up to max_gap_days long. Larger gaps are left as NaN.
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
    """
    result = df.copy()

    target = df[df["station_id"] == target_id][["date", column]].set_index("date")
    ref = df[df["station_id"] == reference_id][["date", column]].set_index("date")

    target.columns = ["target"]
    ref.columns = ["reference"]
    merged = target.join(ref, how="outer")

    valid = merged.dropna()
    if len(valid) < 30:
        print(f"Not enough overlapping data ({len(valid)} points). Need at least 30.")
        return result

    from scipy import stats
    slope, intercept, r_value, _, _ = stats.linregress(valid["reference"], valid["target"])
    print(f"Correlation R2 = {r_value**2:.4f}, slope = {slope:.4f}, intercept = {intercept:.4f}")

    if r_value**2 < 0.7:
        print(f"Warning: weak correlation (R2 = {r_value**2:.4f}). Results may be unreliable.")

    missing = merged["target"].isna() & merged["reference"].notna()
    filled_values = slope * merged.loc[missing, "reference"] + intercept

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

    log_values = np.log1p(values)
    z_scores = np.abs((log_values - log_values.mean()) / log_values.std())
    outlier_idx = z_scores[z_scores > z_threshold].index

    return sdf.loc[outlier_idx]


# ============================================================
# STATISTICS
# ============================================================

def flow_duration_curve(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Compute flow duration curve (FDC) for a station.

    Returns DataFrame with columns: discharge_m3s, exceedance_pct
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
    """Monthly mean, min, max discharge for a station."""
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


# ============================================================
# FLOW INTERPOLATION (metoda interpolacyjna)
# ============================================================

def calc_area_exponent(Q_up: float, A_up: float, Q_down: float, A_down: float) -> float:
    """Calculate catchment area exponent n from two gauging stations.

    n = ln(Q_down / Q_up) / ln(A_down / A_up)
    """
    return np.log(Q_down / Q_up) / np.log(A_down / A_up)


def transfer_flow_single(
    Q_gauge: float, A_gauge: float, A_target: float, n: float = 0.75
) -> float:
    """Transfer flow from one gauge to target using drainage area ratio.

    Q_target = Q_gauge * (A_target / A_gauge)^n

    Args:
        Q_gauge: discharge at gauge [m3/s]
        A_gauge: catchment area at gauge [km2]
        A_target: catchment area at target [km2]
        n: area exponent (default 0.75, or calculate with calc_area_exponent)
    """
    return Q_gauge * (A_target / A_gauge) ** n


def transfer_flow_between(
    Q_up: float, A_up: float,
    Q_down: float, A_down: float,
    A_target: float,
) -> float:
    """Interpolate flow at target between two gauges (metoda interpolacyjna).

    Linear interpolation weighted by catchment area:
    Q_target = Q_up + (Q_down - Q_up) * (A_target - A_up) / (A_down - A_up)

    Args:
        Q_up, A_up: discharge and catchment area at upstream gauge
        Q_down, A_down: discharge and catchment area at downstream gauge
        A_target: catchment area at target location
    """
    return Q_up + (Q_down - Q_up) * (A_target - A_up) / (A_down - A_up)


def transfer_series(
    df: pd.DataFrame,
    station_id: str,
    A_gauge: float,
    A_target: float,
    n: float = 0.75,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Transfer entire discharge time series to target location.

    Returns new DataFrame with recalculated flows.
    """
    result = df[df["station_id"] == station_id].copy()
    result[column] = result[column] * (A_target / A_gauge) ** n
    return result


# ============================================================
# YEAR FILTERING
# ============================================================

def year_completeness(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Calculate completeness per year for a station.

    Returns DataFrame with year, total_days, valid_days, missing_days, pct_valid.
    """
    sdf = df[df["station_id"] == station_id].copy()
    sdf["year"] = sdf["date"].dt.year

    stats = sdf.groupby("year")[column].agg(
        valid_days="count",
        total_days="size",
    )
    stats["missing_days"] = stats["total_days"] - stats["valid_days"]
    stats["pct_valid"] = (stats["valid_days"] / stats["total_days"] * 100).round(1)
    stats.index.name = "year"
    return stats


def identify_flood_years(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
    threshold_factor: float = 3.0,
) -> list[int]:
    """Identify years with extreme floods (annual max >> long-term SWQ).

    A year is flagged if its max flow exceeds threshold_factor * SWQ.

    Returns list of years.
    """
    sdf = df[df["station_id"] == station_id].dropna(subset=[column, "date"]).copy()
    sdf["year"] = sdf["date"].dt.year

    annual_max = sdf.groupby("year")[column].max()
    swq = annual_max.mean()  # SWQ = mean of annual maxima

    flood_years = annual_max[annual_max > threshold_factor * swq].index.tolist()
    return flood_years


def filter_years(
    df: pd.DataFrame,
    station_id: str,
    years_to_remove: list[int],
) -> pd.DataFrame:
    """Remove specified years from a station's data.

    Returns filtered DataFrame (all stations, only specified station's years removed).
    """
    mask = (df["station_id"] == station_id) & (df["date"].dt.year.isin(years_to_remove))
    return df[~mask].reset_index(drop=True)


def filter_incomplete_years(
    df: pd.DataFrame,
    station_id: str,
    min_completeness: float = 0.95,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Remove years with less than min_completeness fraction of valid data.

    Returns filtered DataFrame.
    """
    comp = year_completeness(df, station_id, column)
    incomplete = comp[comp["pct_valid"] < min_completeness * 100].index.tolist()
    if incomplete:
        print(f"Removing {len(incomplete)} incomplete years: {incomplete}")
    return filter_years(df, station_id, incomplete)


# ============================================================
# AVERAGE SORTED YEAR (sredni rok uporzadkowany)
# ============================================================

def sorted_year(
    df: pd.DataFrame,
    station_id: str,
    year: int,
    column: str = "discharge_m3s",
) -> np.ndarray:
    """Get sorted (descending) daily flows for a single year."""
    sdf = df[(df["station_id"] == station_id) & (df["date"].dt.year == year)]
    values = sdf[column].dropna().values
    return np.sort(values)[::-1]


def average_sorted_year(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Calculate average sorted year (sredni rok uporzadkowany).

    For each year:
    1. Sort daily flows from highest to lowest (365 values)
    2. Assign rank 1..365

    Then for each rank position, calculate mean, min, max across all years.
    This gives a smoothed "typical" FDC based on annual averages.

    Returns DataFrame with columns: rank, mean, min, max, std, n_years
    """
    sdf = df[df["station_id"] == station_id].dropna(subset=[column, "date"]).copy()
    sdf["year"] = sdf["date"].dt.year

    years = sdf["year"].unique()
    sorted_arrays = []

    for year in sorted(years):
        vals = sorted_year(df, station_id, year, column)
        if len(vals) >= 360:  # accept years with at least 360 days
            # Resample to exactly 365 values if needed
            if len(vals) != 365:
                x_old = np.linspace(0, 1, len(vals))
                x_new = np.linspace(0, 1, 365)
                vals = np.interp(x_new, x_old, vals)
            sorted_arrays.append(vals)

    if not sorted_arrays:
        return pd.DataFrame()

    matrix = np.array(sorted_arrays)  # shape: (n_years, 365)

    result = pd.DataFrame({
        "rank": np.arange(1, 366),
        "mean": matrix.mean(axis=0).round(3),
        "min": matrix.min(axis=0).round(3),
        "max": matrix.max(axis=0).round(3),
        "std": matrix.std(axis=0).round(3),
        "n_years": len(sorted_arrays),
    })
    # Add exceedance percentage (rank/365 * 100)
    result["exceedance_pct"] = (result["rank"] / 365 * 100).round(2)
    return result

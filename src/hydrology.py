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
# HYDROLOGICAL YEAR
# ============================================================

def hydro_year(dates) -> np.ndarray:
    """Hydrological year for each date (Polish convention: Nov 1 → Oct 31).

    Hydrological year N spans Nov 1 of calendar year N-1 through Oct 31 of
    calendar year N, so November and December belong to the NEXT year's
    hydrological year. IMGW daily files use this convention (month 01 =
    November).

    Args:
        dates: array-like of datetimes (Series, DatetimeIndex, ndarray).

    Returns:
        np.ndarray of int hydrological years.
    """
    dt = pd.DatetimeIndex(dates)
    return (dt.year + (dt.month >= 11).astype(int)).to_numpy()


# ============================================================
# DATA QUALITY
# ============================================================

def check_completeness(df: pd.DataFrame, station_id: str) -> pd.DataFrame:
    """Check data completeness for a station. Returns summary by hydrological year."""
    sdf = df[df["station_id"] == station_id].copy()
    if sdf.empty:
        return pd.DataFrame()

    sdf = sdf.set_index("date").sort_index()
    date_range = pd.date_range(sdf.index.min(), sdf.index.max(), freq="D")
    sdf = sdf.reindex(date_range)

    yearly = sdf.groupby(hydro_year(sdf.index)).agg(
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

    Only fills gaps up to max_gap_days consecutive missing DAYS; longer gaps
    are left entirely as NaN. Note: pandas' interpolate(limit=N) alone is not
    enough — it fills the FIRST N values of every gap regardless of length.
    Gap lengths are measured on a complete daily calendar, so missing rows
    count toward the gap, not only NaN rows.
    """
    result = df.copy()
    mask = result["station_id"] == station_id
    sdf = result.loc[mask].sort_values("date").set_index("date")

    full_range = pd.date_range(sdf.index.min(), sdf.index.max(), freq="D")
    series = sdf[column].reindex(full_range)

    is_missing = series.isna()
    run_id = (is_missing != is_missing.shift()).cumsum()
    run_len = is_missing.groupby(run_id).transform("sum")
    fillable = is_missing & (run_len <= max_gap_days)

    interpolated = series.interpolate(method=method, limit_area="inside")
    series = series.where(~fillable, interpolated)

    result.loc[mask, column] = result.loc[mask, "date"].map(series).values
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
    filled_values = filled_values.clip(lower=0.0)  # discharge cannot be negative

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
# RATING CURVE (KRZYWA KONSUMCYJNA)
# ============================================================

def build_rating_curve(
    df: pd.DataFrame,
    station_id: str,
    degree: int = 2,
    level_col: str = "water_level_cm",
    discharge_col: str = "discharge_m3s",
    fit_H0: bool = True,
) -> dict:
    """Build a rating curve H → Q from paired water level and discharge data.

    Fits a power-law relationship: Q = a * (H - H0)^b
    in log-log space, where H0 is the stage of zero flow (the cease-to-flow
    datum). For lowland gauges H0 is usually NOT zero, so assuming H0=0
    distorts the exponent b and biases reconstructed low flows. When
    fit_H0=True we search H0 in [0, min(H)) for the value maximizing R².

    Falls back to polynomial fit if power-law R² stays below 0.7.

    Args:
        df: DataFrame with station data
        station_id: station ID
        degree: polynomial degree for fallback fit
        level_col: water level column name
        discharge_col: discharge column name
        fit_H0: search for the best zero-flow stage offset (default True).
            Set False to force H0=0 (legacy behavior).

    Returns:
        dict with keys: 'type' ('power' or 'poly'), 'params' (power params
        include 'a', 'b', 'H0'), 'r2', 'n_points', 'H_range', 'Q_range'
    """
    sdf = df[df["station_id"] == station_id][[level_col, discharge_col]].dropna()
    if len(sdf) < 30:
        raise ValueError(
            f"Not enough paired H-Q data ({len(sdf)} points). Need at least 30."
        )

    H = sdf[level_col].values / 100.0  # cm -> m
    Q = sdf[discharge_col].values

    # Power-law fit: Q = a * (H - H0)^b, fitted in log-log space.
    mask = (H > 0) & (Q > 0)
    H_pos, Q_pos = H[mask], Q[mask]

    if len(H_pos) >= 30:
        # Candidate zero-flow offsets: 0 up to just below the lowest stage.
        if fit_H0:
            H0_candidates = np.linspace(0.0, H_pos.min() * 0.95, 40)
        else:
            H0_candidates = np.array([0.0])

        best = None
        for H0 in H0_candidates:
            dH = H_pos - H0
            if np.any(dH <= 0):
                continue
            b, log_a = np.polyfit(np.log(dH), np.log(Q_pos), 1)
            a = np.exp(log_a)
            Q_pred = a * dH ** b
            ss_res = np.sum((Q_pos - Q_pred) ** 2)
            ss_tot = np.sum((Q_pos - Q_pos.mean()) ** 2)
            r2 = 1.0 - ss_res / ss_tot
            if best is None or r2 > best["r2"]:
                best = {"a": float(a), "b": float(b), "H0": float(H0), "r2": float(r2)}

        if best is not None and best["r2"] > 0.7:
            return {
                "type": "power",
                "params": {"a": best["a"], "b": best["b"], "H0": best["H0"]},
                "r2": best["r2"],
                "n_points": len(H_pos),
                "H_range": (float(H.min()), float(H.max())),
                "Q_range": (float(Q.min()), float(Q.max())),
            }

    # Fallback: polynomial fit
    coeffs = np.polyfit(H, Q, degree)
    Q_pred = np.polyval(coeffs, H)
    ss_res = np.sum((Q - Q_pred) ** 2)
    ss_tot = np.sum((Q - Q.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot

    return {
        "type": "poly",
        "params": {"coefficients": coeffs.tolist(), "degree": degree},
        "r2": r2,
        "n_points": len(H),
        "H_range": (float(H.min()), float(H.max())),
        "Q_range": (float(Q.min()), float(Q.max())),
    }


def apply_rating_curve(H_values: np.ndarray, rating: dict) -> np.ndarray:
    """Apply rating curve to convert water levels [m] to discharge [m3/s].

    Args:
        H_values: water levels in meters
        rating: dict from build_rating_curve()

    Returns:
        Estimated discharge values
    """
    if rating["type"] == "power":
        a, b = rating["params"]["a"], rating["params"]["b"]
        H0 = rating["params"].get("H0", 0.0)  # zero-flow stage offset
        Q = a * np.maximum(H_values - H0, 0.001) ** b
    else:
        Q = np.polyval(rating["params"]["coefficients"], H_values)

    return np.maximum(Q, 0.0)  # discharge cannot be negative


def reconstruct_discharge(
    df: pd.DataFrame,
    station_id: str,
    rating: dict,
    level_col: str = "water_level_cm",
    discharge_col: str = "discharge_m3s",
) -> pd.DataFrame:
    """Reconstruct missing discharge from water level using a rating curve.

    Only fills rows where discharge is NaN but water level is available.

    Args:
        df: DataFrame with station data
        station_id: station ID
        rating: dict from build_rating_curve()
        level_col: water level column name
        discharge_col: discharge column name

    Returns:
        DataFrame with filled discharge values
    """
    result = df.copy()
    mask = (result["station_id"] == station_id)
    sdf = result.loc[mask].copy()

    # Find rows with missing Q but available H
    fillable = sdf[discharge_col].isna() & sdf[level_col].notna()
    n_fillable = fillable.sum()

    if n_fillable == 0:
        print(f"No missing discharge values with available water levels.")
        return result

    H_m = sdf.loc[fillable, level_col].values / 100.0  # cm -> m
    Q_est = apply_rating_curve(H_m, rating)

    sdf.loc[fillable, discharge_col] = Q_est
    result.loc[mask, discharge_col] = sdf[discharge_col].values

    print(f"Reconstructed {n_fillable} discharge values from water levels "
          f"(rating curve R2 = {rating['r2']:.4f})")
    return result


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
    # Annual extremes (SNQ/SWQ) follow the hydrological year (Nov-Oct), so a
    # winter season is never split across two "years".
    annual = sdf_valid.groupby(hydro_year(sdf_valid["date"]))[column]

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
    """Annual mean, min, max discharge for a station (hydrological years)."""
    sdf = df[df["station_id"] == station_id].dropna(subset=[column, "date"]).copy()
    sdf["year"] = hydro_year(sdf["date"])

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

    Raises:
        ValueError: if areas are non-positive, equal (no area gradient), or
            flows are non-positive (log undefined).

    Note: numerically UNSTABLE when A_down ≈ A_up (tiny denominator amplifies
    noise in Q_down/Q_up). For nearly equal catchments prefer a single
    long-term exponent or linear interpolation (see transfer_flow_between).
    """
    if A_up <= 0 or A_down <= 0:
        raise ValueError(f"Catchment areas must be positive (got A_up={A_up}, A_down={A_down}).")
    if A_down == A_up:
        raise ValueError("Cannot compute area exponent: A_up == A_down (no area gradient).")
    if Q_up <= 0 or Q_down <= 0:
        raise ValueError(f"Flows must be positive for log-ratio (got Q_up={Q_up}, Q_down={Q_down}).")
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

    Raises:
        ValueError: if A_down == A_up (zero area gradient → divide-by-zero).
    """
    if A_down == A_up:
        raise ValueError("Cannot interpolate: A_up == A_down (zero area gradient).")
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
    """Calculate completeness per hydrological year (Nov-Oct) for a station.

    Returns DataFrame with year, total_days, valid_days, missing_days, pct_valid.
    """
    sdf = df[df["station_id"] == station_id].copy()
    sdf["year"] = hydro_year(sdf["date"])

    valid_days = sdf.groupby("year")[column].agg(valid_days="count")
    # Hydro year N contains Feb of calendar year N, so its length is 366
    # exactly when calendar year N is a leap year.
    expected = pd.Series(
        {y: 366 if pd.Timestamp(year=y, month=1, day=1).is_leap_year else 365
         for y in valid_days.index},
        name="expected_days",
    )
    stats = valid_days.copy()
    stats["expected_days"] = expected
    stats["missing_days"] = stats["expected_days"] - stats["valid_days"]
    stats["pct_valid"] = (stats["valid_days"] / stats["expected_days"] * 100).round(1)
    stats.index.name = "year"
    return stats


def identify_flood_years(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
    threshold_factor: float = 3.0,
) -> list[int]:
    """Identify hydrological years with extreme floods (annual max >> long-term SWQ).

    A year is flagged if its max flow exceeds threshold_factor * SWQ.

    Returns list of hydrological years (e.g. the July 1997 Odra flood → 1997).
    """
    sdf = df[df["station_id"] == station_id].dropna(subset=[column, "date"]).copy()
    sdf["year"] = hydro_year(sdf["date"])

    annual_max = sdf.groupby("year")[column].max()
    swq = annual_max.mean()  # SWQ = mean of annual maxima

    flood_years = annual_max[annual_max > threshold_factor * swq].index.tolist()
    return flood_years


def filter_years(
    df: pd.DataFrame,
    station_id: str,
    years_to_remove: list[int],
) -> pd.DataFrame:
    """Remove specified hydrological years from a station's data.

    Returns filtered DataFrame (all stations, only specified station's years removed).
    """
    years_arr = pd.Series(hydro_year(df["date"]), index=df.index)
    mask = (df["station_id"] == station_id) & (years_arr.isin(years_to_remove))
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
    """Get sorted (descending) daily flows for a single hydrological year."""
    sdf = df[(df["station_id"] == station_id) & (hydro_year(df["date"]) == year)]
    values = sdf[column].dropna().values
    return np.sort(values)[::-1]


def average_sorted_year(
    df: pd.DataFrame,
    station_id: str,
    column: str = "discharge_m3s",
) -> pd.DataFrame:
    """Calculate average sorted year (sredni rok uporzadkowany).

    Years are hydrological years (Nov-Oct).

    For each year:
    1. Sort daily flows from highest to lowest
    2. Resample to **exactly 365 rank positions** (Feb 29 is dropped from leap
       years — see note below)

    Then for each rank position, calculate mean, min, max across all years.
    This gives a smoothed "typical" FDC based on annual averages.

    Note on the 365-day convention:
        Leap years contribute 366 sorted values which are interpolated down to
        365. The annual energy estimate sum(P_kW)*24h works over the 365 ranks
        = 8760 hours/year, which matches the denominator used in
        `capacity_factor` (P_rated * 8760). Internally consistent; ignores one
        day every four years (≈ 0.07% bias).

    Returns DataFrame with columns: rank, mean, min, max, std, n_years
    """
    sdf = df[df["station_id"] == station_id].dropna(subset=[column, "date"]).copy()
    sdf["year"] = hydro_year(sdf["date"])

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


# ============================================================
# ENVIRONMENTAL FLOW (A2) — Polish "nienaruszalny przeplyw"
# ============================================================

def environmental_flow(
    Q_sorted: np.ndarray,
    method: str = "Q90",
    multiplier: float = 1.0,
    mar_fraction: float = 0.10,
) -> float:
    """Estimate environmental (biological) flow requirement [m³/s].

    Polish water law (Prawo wodne 2017) requires a minimum biological flow —
    'nienaruszalny przeplyw' — that must remain in the river bed regardless
    of plant operation. Common rules:

        'Q90' (default)  flow exceeded 90% of the time; common baseline.
        'Q95'            stricter (5% of year); for sensitive streams.
        'Q_med'          0.5 × median (Tennant 'fair habitat'); 50/30/10 rule.
        'MAR'            mar_fraction × mean annual runoff (default 10% MAR).

    Args:
        Q_sorted: average sorted year flows (descending), or equivalent FDC.
        method: 'Q90', 'Q95', 'Q_med', or 'MAR'.
        multiplier: scale factor on the chosen statistic (e.g. 1.5 for fish migration).
        mar_fraction: used only when method='MAR'.

    Returns:
        Environmental flow [m³/s] (single scalar).
    """
    Q_sorted = np.asarray(Q_sorted, dtype=float)
    if Q_sorted.size == 0:
        raise ValueError("Q_sorted is empty.")
    n = Q_sorted.size
    if method == "Q90":
        return float(Q_sorted[min(int(0.90 * n), n - 1)] * multiplier)
    if method == "Q95":
        return float(Q_sorted[min(int(0.95 * n), n - 1)] * multiplier)
    if method == "Q_med":
        return float(Q_sorted[min(int(0.50 * n), n - 1)] * 0.5 * multiplier)
    if method == "MAR":
        return float(Q_sorted.mean() * mar_fraction)
    raise ValueError(f"Unknown method: {method!r}. Choose Q90 / Q95 / Q_med / MAR.")


# ============================================================
# EW LOCATION INTERPOLATION (D1) — single source of truth
# ============================================================

def interpolate_q_to_location(
    Q_up: np.ndarray,
    Q_down: np.ndarray,
    A_up: float,
    A_down: float,
    A_target: float,
    method: str = "daily_n",
) -> np.ndarray:
    """Interpolate discharge from two gauges to an intermediate target location.

    Three methods:

        'daily_n'  (default; matches WPE_2.xlsm)
            Per-day power-law exponent:
                n(t) = ln(Q_down(t) / Q_up(t)) / ln(A_down / A_up)
                Q_target(t) = Q_up(t) · (A_target / A_up) ** n(t)
            ⚠ NUMERICALLY UNSTABLE when A_down ≈ A_up — the small denominator
            amplifies noise in Q_down/Q_up. Use only when catchments differ
            substantially. See nb 05's three-method comparison.

        'global_n'
            Same formula but with a SINGLE exponent computed from period means:
                n = ln(mean(Q_down) / mean(Q_up)) / ln(A_down / A_up)
            Stable; loses per-day variability of the scaling.

        'linear'
            Linear interpolation by catchment area (no logarithms):
                Q_target(t) = Q_up(t) + (Q_down(t) − Q_up(t)) · (A_target − A_up)/(A_down − A_up)
            Most intuitive; treats Q as varying linearly with A in time slice.

    Args:
        Q_up, Q_down: paired time series at the two gauges (must be aligned).
        A_up, A_down, A_target: catchment areas (any consistent unit, e.g. km²).
            Constraint: A_down ≠ A_up (zero area gradient → undefined).
        method: 'daily_n', 'global_n', or 'linear'.

    Returns:
        Q at target location [same units as Q_up/Q_down], numpy array.
    """
    Q_up = np.asarray(Q_up, dtype=float)
    Q_down = np.asarray(Q_down, dtype=float)
    if A_down == A_up:
        raise ValueError("Cannot interpolate: A_up == A_down (zero area gradient).")
    if A_up <= 0 or A_down <= 0 or A_target <= 0:
        raise ValueError(
            f"Catchment areas must be positive (A_up={A_up}, A_down={A_down}, A_target={A_target})."
        )
    if Q_up.shape != Q_down.shape:
        raise ValueError(f"Shape mismatch: Q_up{Q_up.shape} vs Q_down{Q_down.shape}.")

    if method == "daily_n":
        ln_A = np.log(A_down / A_up)
        # Suppress warnings on Q ≤ 0; consumer should pre-clean. Result will be NaN there.
        with np.errstate(divide="ignore", invalid="ignore"):
            n = np.log(Q_down / Q_up) / ln_A
            return Q_up * (A_target / A_up) ** n
    if method == "global_n":
        ln_A = np.log(A_down / A_up)
        Q_up_mean = float(np.nanmean(Q_up))
        Q_down_mean = float(np.nanmean(Q_down))
        if Q_up_mean <= 0 or Q_down_mean <= 0:
            raise ValueError("Mean flows must be positive for global_n method.")
        n_global = np.log(Q_down_mean / Q_up_mean) / ln_A
        return Q_up * (A_target / A_up) ** n_global
    if method == "linear":
        w = (A_target - A_up) / (A_down - A_up)
        return Q_up + (Q_down - Q_up) * w

    raise ValueError(f"Unknown method: {method!r}. Choose daily_n / global_n / linear.")

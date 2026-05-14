"""
Production Calculation Module
===============================
Assembles hydraulic loss, turbine efficiency, and generator efficiency models
into a full power and energy calculation for the average sorted year (365 days).

This module is the integration layer — it does not define new models,
but combines models from src/losses, src/turbine, and src/generator.

Main function: compute_power() takes sorted year data + selected models
and returns a DataFrame with daily power, efficiency, and energy.
"""

import numpy as np
import pandas as pd
from typing import Callable

from src.turbine import TurbineType, turbine_efficiency, dispatch_flow
from src.generator import generator_efficiency
from src.losses import total_head_loss


# ============================================================
# CORE POWER CALCULATION
# ============================================================

def compute_power(
    Q_sorted: np.ndarray,
    H_gross: np.ndarray,
    Q_design: float,
    n_turbines: int,
    turbine_type: TurbineType,
    loss_fns: list[Callable] | None = None,
    H_design: float | None = None,
    gen_k_cu: float = 0.025,
    gen_k_fe: float = 0.010,
    gen_k_mech: float = 0.005,
    rho: float = 998.0,
    g: float = 9.81,
) -> pd.DataFrame:
    """Full power calculation for average sorted year with variable efficiencies.

    Calculation chain for each day:
        1. Dispatch flow among turbines → Q_per_turbine, n_active
        2. Compute head losses on Q_used (= n_active × Q_per_turbine)
           → H_net = H_gross − ΔH
        3. Turbine efficiency → η_t(Q_per_turbine / Q_design)
        4. Shaft power → P_shaft = n_active · ρ·g·Q_per_turb·H_net·η_t
        5. Generator efficiency η_g uses *per-unit* load:
              P_ratio = (P_shaft / n_active) / P_rated_unit
           so that a single turbine running near its rating sees η_g(1.0),
           not a fleet-averaged value.
        6. P_el = P_shaft · η_g     7. E = P_el · 24 h

    Args:
        Q_sorted: sorted year flows [m³/s], shape (n_days,), descending
        H_gross: gross head per day [m], shape (n_days,) or scalar
        Q_design: design flow **per turbine** [m³/s]
        n_turbines: number of identical turbines installed
        turbine_type: TurbineType from catalog
        loss_fns: list of head-loss callables Q→ΔH (from src/losses).
                  None = no hydraulic losses (H_net = H_gross)
        H_design: head at the design point [m]. Used to compute the
                  per-unit rated shaft power. If None, max(H_gross) is used.
        gen_k_cu, gen_k_fe, gen_k_mech: generator loss coefficients
        rho, g: water density and gravitational acceleration

    Returns:
        DataFrame columns:
            day, pct, Q_avail, Q_per_turbine, n_active, Q_used,
            H_gross, H_net, eta_t, P_shaft_kW, eta_g, P_el_kW, E_kWh
    """
    Q_sorted = np.asarray(Q_sorted, dtype=float)
    H_gross = np.broadcast_to(np.asarray(H_gross, dtype=float), Q_sorted.shape).copy()
    n_days = len(Q_sorted)

    # Step 1: Dispatch
    Q_per_turb, n_active = dispatch_flow(Q_sorted, Q_design, n_turbines, turbine_type)
    Q_used = Q_per_turb * n_active

    # Step 2: Head losses
    if loss_fns:
        dH = total_head_loss(Q_used, loss_fns)
        H_net = np.maximum(H_gross - dH, 0.0)
    else:
        H_net = H_gross.copy()

    # Step 3: Turbine efficiency (Q_ratio is per-unit by construction)
    Q_ratio = np.where(Q_design > 0, Q_per_turb / Q_design, 0.0)
    eta_t = turbine_efficiency(Q_ratio, turbine_type)

    # Step 4: Shaft power (fleet total = n_active × per-unit power)
    P_shaft_kW = n_active * rho * g * Q_per_turb * H_net * eta_t / 1000.0

    # Step 5: Generator efficiency — uses PER-UNIT load
    if H_design is None:
        H_design = float(np.max(H_gross)) if H_gross.size > 0 else 0.0
    P_rated_unit_kW = rho * g * Q_design * H_design * turbine_type.eta_peak / 1000.0
    # per-unit shaft power = total / n_active (avoid div-by-zero when shut down)
    P_shaft_per_unit_kW = np.where(
        n_active > 0, P_shaft_kW / np.maximum(n_active, 1), 0.0,
    )
    P_ratio = np.where(P_rated_unit_kW > 0, P_shaft_per_unit_kW / P_rated_unit_kW, 0.0)
    eta_g = generator_efficiency(P_ratio, gen_k_cu, gen_k_fe, gen_k_mech)

    # Step 6: Electrical power
    P_el_kW = P_shaft_kW * eta_g

    # Step 7: Daily energy
    E_kWh = P_el_kW * 24.0

    return pd.DataFrame({
        "day": np.arange(1, n_days + 1),
        "pct": np.round(np.arange(1, n_days + 1) / n_days * 100, 2),
        "Q_avail": Q_sorted,
        "Q_per_turbine": Q_per_turb,
        "n_active": n_active,
        "Q_used": Q_used,
        "H_gross": H_gross,
        "H_net": H_net,
        "eta_t": np.round(eta_t, 4),
        "P_shaft_kW": np.round(P_shaft_kW, 2),
        "eta_g": np.round(eta_g, 4),
        "P_el_kW": np.round(P_el_kW, 2),
        "E_kWh": np.round(E_kWh, 2),
    })


# ============================================================
# SUMMARY METRICS
# ============================================================

def annual_energy(power_df: pd.DataFrame) -> float:
    """Annual energy production [MWh/year]."""
    return power_df["E_kWh"].sum() / 1000.0


def capacity_factor(power_df: pd.DataFrame, P_rated_kW: float) -> float:
    """Capacity factor [-].

    CF = E_actual / E_theoretical
    E_theoretical = P_rated * 8760h
    """
    E_max = P_rated_kW * 8760  # kWh
    if E_max <= 0:
        return 0.0
    return power_df["E_kWh"].sum() / E_max


def operating_hours(power_df: pd.DataFrame) -> int:
    """Number of operating days (P > 0)."""
    return int((power_df["P_el_kW"] > 0).sum())


def average_efficiency(power_df: pd.DataFrame) -> dict:
    """Average turbine and generator efficiency (weighted by energy)."""
    mask = power_df["P_el_kW"] > 0
    if mask.sum() == 0:
        return {"eta_t_avg": 0.0, "eta_g_avg": 0.0, "eta_total_avg": 0.0}

    E = power_df.loc[mask, "E_kWh"]
    eta_t_avg = np.average(power_df.loc[mask, "eta_t"], weights=E)
    eta_g_avg = np.average(power_df.loc[mask, "eta_g"], weights=E)

    return {
        "eta_t_avg": round(eta_t_avg, 4),
        "eta_g_avg": round(eta_g_avg, 4),
        "eta_total_avg": round(eta_t_avg * eta_g_avg, 4),
    }


# ============================================================
# CONSTANT-EFFICIENCY CALCULATION (for comparison with nb05)
# ============================================================

def compute_power_constant_eta(
    Q_sorted: np.ndarray,
    H_gross: np.ndarray,
    Q_design: float,
    n_turbines: int,
    Q_min_fraction: float = 0.15,
    eta_total: float = 0.848,
    rho: float = 998.0,
    g: float = 9.81,
) -> pd.DataFrame:
    """Simplified power calculation with constant total efficiency.

    Reproduces the approach from notebook 05 for comparison.
    No head losses, no part-load efficiency variation.

    Args:
        Q_sorted: sorted year flows [m³/s]
        H_gross: gross head [m] (scalar or array)
        Q_design: total design flow [m³/s] (all turbines combined)
        n_turbines: number of turbines (for Q_min only)
        Q_min_fraction: minimum Q/Q_design for operation
        eta_total: constant total efficiency
        rho, g: physical constants

    Returns:
        DataFrame with columns: day, pct, Q_avail, Q_used, H, P_kW, E_kWh
    """
    Q_sorted = np.asarray(Q_sorted, dtype=float)
    H = np.broadcast_to(np.asarray(H_gross, dtype=float), Q_sorted.shape).copy()
    n_days = len(Q_sorted)

    Q_min = Q_min_fraction * Q_design
    mask = Q_sorted >= Q_min
    Q_used = np.where(mask, np.minimum(Q_sorted, Q_design), 0.0)

    P_kW = rho * g * Q_used * H * eta_total / 1000.0
    E_kWh = P_kW * 24.0

    return pd.DataFrame({
        "day": np.arange(1, n_days + 1),
        "pct": np.round(np.arange(1, n_days + 1) / n_days * 100, 2),
        "Q_avail": Q_sorted,
        "Q_used": Q_used,
        "H": H,
        "P_kW": np.round(P_kW, 2),
        "E_kWh": np.round(E_kWh, 2),
    })

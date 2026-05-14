"""
Turbine Module
===============
Turbine catalog, efficiency models, dimensional design, and multi-turbine dispatch.

Turbine types: Kaplan, Francis, Propeller (fixed blade), Crossflow (Banki-Michell).
Efficiency curves stored as data points (Q/Q_design, eta) for interpolation.

Unit parameters (similarity laws):
    Q = Q11 * D1^2 * sqrt(H)
    n = n11 * sqrt(H) / D1
    nsN = n * sqrt(P) / H^(5/4)     [specific speed, P in kW]

Reference: ESHA Guide (2004), Penche (2004), WPE_2.xlsm TurbineSelection
"""

import numpy as np
from dataclasses import dataclass


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class TurbineType:
    """Turbine type specification.

    Attributes:
        name: short identifier (e.g. 'kaplan')
        name_pl: Polish display name
        Q11: unit discharge [m³/s] (similarity parameter)
        n11: unit speed [rpm] (similarity parameter)
        eta_peak: peak efficiency [-]
        eta_curve_q: tuple of Q/Q_design values for efficiency curve
        eta_curve_eta: tuple of corresponding efficiency values
        Q_ratio_min: minimum Q/Q_design for operation
        Q_ratio_max: maximum Q/Q_design for operation
        H_range: (H_min, H_max) applicable head range [m]
    """
    name: str
    name_pl: str
    Q11: float
    n11: float
    eta_peak: float
    eta_curve_q: tuple
    eta_curve_eta: tuple
    Q_ratio_min: float
    Q_ratio_max: float
    H_range: tuple[float, float]


# ============================================================
# TURBINE CATALOG
# ============================================================

TURBINE_CATALOG: dict[str, TurbineType] = {

    "kaplan": TurbineType(
        name="kaplan",
        name_pl="Kaplan (podwojnie regulowana)",
        Q11=1.2,
        n11=158.0,
        eta_peak=0.92,
        eta_curve_q=(0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.10),
        eta_curve_eta=(0.50, 0.65, 0.78, 0.85, 0.88, 0.90, 0.91, 0.92, 0.92, 0.91, 0.88),
        Q_ratio_min=0.15,
        Q_ratio_max=1.10,
        H_range=(1.0, 20.0),
    ),

    "francis": TurbineType(
        name="francis",
        name_pl="Francis",
        Q11=0.8,
        n11=120.0,
        eta_peak=0.93,
        eta_curve_q=(0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00),
        eta_curve_eta=(0.60, 0.75, 0.84, 0.89, 0.92, 0.93, 0.93, 0.91),
        Q_ratio_min=0.40,
        Q_ratio_max=1.00,
        H_range=(10.0, 350.0),
    ),

    "propeller": TurbineType(
        name="propeller",
        name_pl="Smiglowa (stale lopaty)",
        Q11=1.05,
        n11=133.0,
        eta_peak=0.90,
        eta_curve_q=(0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00),
        eta_curve_eta=(0.40, 0.55, 0.68, 0.78, 0.85, 0.89, 0.90, 0.88),
        Q_ratio_min=0.65,
        Q_ratio_max=1.00,
        H_range=(1.0, 15.0),
    ),

    "crossflow": TurbineType(
        name="crossflow",
        name_pl="Przeplywowa (Banki-Michell)",
        Q11=0.45,
        n11=40.0,
        eta_peak=0.84,
        eta_curve_q=(0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00),
        eta_curve_eta=(0.55, 0.65, 0.72, 0.78, 0.80, 0.82, 0.83, 0.84, 0.84, 0.83, 0.82),
        Q_ratio_min=0.10,
        Q_ratio_max=1.00,
        H_range=(1.0, 200.0),
    ),

    # Specific models from WPE_2.xlsm
    "pl10": TurbineType(
        name="pl10",
        name_pl="PL 10 (Kaplan)",
        Q11=1.2,
        n11=158.0,
        eta_peak=0.876,
        eta_curve_q=(0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00),
        eta_curve_eta=(0.45, 0.58, 0.70, 0.78, 0.83, 0.86, 0.87, 0.876, 0.87, 0.85),
        Q_ratio_min=0.15,
        Q_ratio_max=1.00,
        H_range=(1.0, 20.0),
    ),

    "pl20": TurbineType(
        name="pl20",
        name_pl="PL 20 (Kaplan)",
        Q11=1.05,
        n11=133.0,
        eta_peak=0.90,
        eta_curve_q=(0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00),
        eta_curve_eta=(0.60, 0.72, 0.80, 0.85, 0.88, 0.89, 0.90, 0.90, 0.89, 0.87),
        Q_ratio_min=0.20,
        Q_ratio_max=1.00,
        H_range=(1.0, 20.0),
    ),
}


def get_turbine_types() -> dict[str, TurbineType]:
    """Return the full turbine catalog."""
    return TURBINE_CATALOG.copy()


# ============================================================
# EFFICIENCY MODEL
# ============================================================

def turbine_efficiency(
    Q_ratio: np.ndarray,
    turbine_type: TurbineType,
) -> np.ndarray:
    """Turbine efficiency as function of relative flow Q/Q_design.

    Interpolates the efficiency curve stored in the TurbineType.
    Returns 0 outside the operating range [Q_ratio_min, Q_ratio_max].

    Args:
        Q_ratio: Q / Q_design [-] (scalar or array)
        turbine_type: TurbineType from catalog

    Returns:
        Efficiency eta_t [-] (same shape as Q_ratio)
    """
    Q_ratio = np.asarray(Q_ratio, dtype=float)
    q_pts = np.array(turbine_type.eta_curve_q)
    e_pts = np.array(turbine_type.eta_curve_eta)

    # Interpolate
    eta = np.interp(Q_ratio, q_pts, e_pts, left=0.0, right=0.0)

    # Zero outside operating range
    mask = (Q_ratio < turbine_type.Q_ratio_min) | (Q_ratio > turbine_type.Q_ratio_max)
    eta = np.where(mask, 0.0, eta)

    return eta


# ============================================================
# DIMENSIONAL DESIGN (similarity laws)
# ============================================================

def runner_diameter(
    Q_design: float,
    H: float,
    turbine_type: TurbineType,
) -> float:
    """Runner diameter from similarity laws.

    D1 = sqrt(Q_design / (Q11 * sqrt(H)))

    Args:
        Q_design: design flow per turbine [m³/s]
        H: design head [m]
        turbine_type: TurbineType from catalog

    Returns:
        Runner diameter D1 [m]
    """
    return np.sqrt(Q_design / (turbine_type.Q11 * np.sqrt(H)))


def rotational_speed(
    H: float,
    D1: float,
    turbine_type: TurbineType,
) -> float:
    """Rotational speed from similarity laws.

    n = n11 * sqrt(H) / D1

    Args:
        H: design head [m]
        D1: runner diameter [m]
        turbine_type: TurbineType from catalog

    Returns:
        Rotational speed n [rpm]
    """
    return turbine_type.n11 * np.sqrt(H) / D1


def synchronous_speed(n_raw: float, f: float = 50.0) -> tuple[float, int]:
    """Find nearest synchronous speed and number of pole pairs.

    n_sync = 60 * f / p, where p = number of pole pairs.

    Args:
        n_raw: target rotational speed [rpm]
        f: grid frequency [Hz] (default 50 Hz)

    Returns:
        (n_sync, n_poles) — synchronous speed [rpm] and number of poles
    """
    # Possible pole numbers (even: 4, 6, 8, ..., 30)
    best_n, best_poles = 0.0, 4
    best_diff = float("inf")
    for poles in range(4, 32, 2):
        n_sync = 60 * f / (poles / 2)
        diff = abs(n_sync - n_raw)
        if diff < best_diff:
            best_diff = diff
            best_n = n_sync
            best_poles = poles
    return best_n, best_poles


def specific_speed(
    n: float,
    P_kW: float,
    H: float,
) -> float:
    """Specific speed (predkosc szybkobieznosci).

    nsN = n * sqrt(P) / H^(5/4)

    where P is in kW, n in rpm, H in m.

    Args:
        n: rotational speed [rpm]
        P_kW: power [kW]
        H: head [m]

    Returns:
        Specific speed nsN [-]
    """
    return n * np.sqrt(P_kW) / H ** (5 / 4)


# ============================================================
# TURBINE APPLICABILITY
# ============================================================

def filter_applicable_turbines(
    H: float,
    Q_design: float,
    catalog: dict[str, TurbineType] | None = None,
) -> dict[str, TurbineType]:
    """Filter turbine types applicable for given head and design flow.

    Checks if H falls within the turbine's H_range.

    Args:
        H: design head [m]
        Q_design: design flow [m³/s]
        catalog: turbine catalog (default: TURBINE_CATALOG)

    Returns:
        Dict of applicable TurbineType entries
    """
    if catalog is None:
        catalog = TURBINE_CATALOG
    result = {}
    for name, ttype in catalog.items():
        H_min, H_max = ttype.H_range
        if H_min <= H <= H_max:
            result[name] = ttype
    return result


# ============================================================
# MULTI-TURBINE DISPATCH
# ============================================================

def dispatch_flow(
    Q_available: np.ndarray,
    Q_design: float,
    n_turbines: int,
    turbine_type: TurbineType,
) -> tuple[np.ndarray, np.ndarray]:
    """Dispatch available flow among identical turbines.

    Strategy: use minimum number of turbines at highest load.
    Starting from all n_turbines, reduce count if Q per turbine
    falls below Q_min. Cap each turbine at Q_design.

    Args:
        Q_available: available flow [m³/s] (array, shape (n_days,))
        Q_design: design flow per turbine [m³/s]
        n_turbines: number of installed turbines
        turbine_type: TurbineType (for Q_ratio_min)

    Returns:
        (Q_per_turbine, n_active):
            Q_per_turbine — flow through each active turbine [m³/s], shape (n_days,)
            n_active — number of active turbines per day, shape (n_days,)
    """
    Q = np.asarray(Q_available, dtype=float)
    Q_min = turbine_type.Q_ratio_min * Q_design

    Q_per = np.zeros_like(Q)
    n_active = np.zeros_like(Q, dtype=int)

    for n in range(n_turbines, 0, -1):
        Q_each = Q / n
        # This config works where Q_each >= Q_min and we haven't assigned yet
        can_run = (Q_each >= Q_min) & (n_active == 0)
        Q_per = np.where(can_run, np.minimum(Q_each, Q_design), Q_per)
        n_active = np.where(can_run, n, n_active)

    return Q_per, n_active

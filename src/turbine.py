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
        Q_max: maximum design flow PER UNIT [m³/s] — technology envelope.
            E.g. crossflow (Banki-Michell) units are built up to ~13 m³/s;
            sizing one for 50 m³/s is physically meaningless even though
            its H_range would allow it.
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
    Q_max: float = float("inf")


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
        Q_max=250.0,   # largest low-head Kaplan/bulb units
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
        Q_max=200.0,
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
        Q_max=100.0,
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
        Q_max=13.0,    # Banki-Michell units top out around 10-13 m³/s
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
        Q_max=250.0,
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
        Q_max=250.0,
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


def synchronous_speed(
    n_raw: float,
    f: float = 50.0,
    mode: str = "nearest",
    max_poles: int = 60,
) -> tuple[float, int]:
    """Snap an ideal rotational speed to an achievable grid synchronous speed.

    A grid-connected synchronous machine locks to discrete speeds:
        n_sync = 60 * f / p_pairs,   p_pairs = poles / 2  (poles always even)

    Args:
        n_raw: target (ideal) rotational speed [rpm] from similarity laws
        f: grid frequency [Hz] (default 50 Hz)
        mode: how to choose among achievable speeds:
            'nearest' — closest synchronous speed (default)
            'lower'   — highest n_sync <= n_raw (conservative: slower runner,
                        larger D1, safe against under-sizing the flow path)
            'higher'  — lowest n_sync >= n_raw
        max_poles: largest pole count considered (default 60 → n_sync down to
            100 rpm at 50 Hz, covering slow low-head hydro machines).
            NOTE: the old version stopped at 30 poles (200 rpm) and silently
            clamped slow machines — extended here.

    Returns:
        (n_sync, n_poles) — synchronous speed [rpm] and number of POLES (even)

    Note:
        In practice the engineer picks a synchronous speed, then RESIZES the
        runner D1 so it passes Q_design at H_design. A lower speed → larger,
        slower runner (conservative). 'nearest' is the usual first guess —
        always verify the resulting nsN stays inside the turbine's range.
    """
    candidates = [(60 * f / (poles / 2), poles) for poles in range(2, max_poles + 1, 2)]

    if mode == "lower":
        feasible = [c for c in candidates if c[0] <= n_raw]
        chosen = max(feasible, key=lambda c: c[0]) if feasible else min(candidates, key=lambda c: c[0])
    elif mode == "higher":
        feasible = [c for c in candidates if c[0] >= n_raw]
        chosen = min(feasible, key=lambda c: c[0]) if feasible else max(candidates, key=lambda c: c[0])
    else:  # 'nearest'
        chosen = min(candidates, key=lambda c: abs(c[0] - n_raw))

    return chosen


def specific_speed(
    n: float,
    P_kW: float,
    H: float,
    metric_hp: bool = False,
) -> float:
    """Specific speed (wyroznik szybkobieznosci).

    nsN = n * sqrt(P) / H^(5/4)

    Args:
        n: rotational speed [rpm]
        P_kW: power [kW]
        H: head [m]
        metric_hp: if True, multiply by 1.166 to convert kW under sqrt into
            metric horsepower units — matches WPE_2.xlsm and classical European
            hydropower tables (e.g. Penche 2004, Czekalski 2008).

    Returns:
        Specific speed nsN [-]
    """
    factor = 1.166 if metric_hp else 1.0
    return factor * n * np.sqrt(P_kW) / H ** (5 / 4)


# ============================================================
# CAVITATION (Thoma sigma) — A1
# ============================================================

def atmospheric_pressure_head(elevation_m: float = 0.0) -> float:
    """Atmospheric pressure expressed as head of water column [m].

    Linear approximation: H_atm ≈ 10.33 - elevation/900 (valid below ~2000 m).
    Sea level (z=0): 10.33 m.
    """
    return max(10.33 - elevation_m / 900.0, 0.0)


def vapor_pressure_head(water_temp_C: float = 10.0) -> float:
    """Saturated water-vapor pressure expressed as head [m].

    Approximation (Antoine-like): H_v ≈ 0.0625 · exp(0.0683·T) [T in °C].
    Examples: T=5°C→0.088 m, 10°C→0.124 m, 15°C→0.174 m, 20°C→0.245 m.
    """
    return 0.0625 * np.exp(0.0683 * water_temp_C)


def thoma_sigma_critical(nsN_metric_hp: float, turbine_key: str) -> float:
    """Critical Thoma cavitation coefficient σ_c as a function of specific speed.

    Empirical formulas (Penche 2004, Czekalski 2008) using nsN in metric-HP form
    (the WPE_2 ×1.166 convention):

        Pelton:          σ_c = 0          (impulse turbine, no cavitation risk)
        Francis:         σ_c = 7.54e-5 · nsN^1.41
        Kaplan / prop.:  σ_c = 4.41e-9 · nsN^2.81

    σ_actual must exceed σ_c — otherwise cavitation pits the runner.

    Args:
        nsN_metric_hp: specific speed in metric HP form (multiply kW-form by 1.166)
        turbine_key: 'pelton', 'francis', 'kaplan', 'propeller', 'semi_kaplan',
                     'crossflow', or one of the PL10/PL20 catalog entries.
    """
    if turbine_key == "pelton":
        return 0.0
    if turbine_key == "francis":
        return 7.54e-5 * nsN_metric_hp ** 1.41
    if turbine_key in ("kaplan", "pl10", "pl20", "propeller", "semi_kaplan", "crossflow"):
        return 4.41e-9 * nsN_metric_hp ** 2.81
    raise ValueError(f"Unknown turbine type for cavitation: {turbine_key!r}")


def thoma_sigma(
    H_s_m: float,
    H_net_m: float,
    elevation_m: float = 0.0,
    water_temp_C: float = 10.0,
) -> float:
    """Actual Thoma cavitation coefficient σ for an installation.

        σ = (H_atm - H_v - H_s) / H_net

    H_s is the **suction head** = height of runner centerline above tailwater
    (positive when above; negative when submerged below tailwater = safer).
    """
    H_atm = atmospheric_pressure_head(elevation_m)
    H_v = vapor_pressure_head(water_temp_C)
    return (H_atm - H_v - H_s_m) / H_net_m


def suction_head_max(
    nsN_metric_hp: float,
    H_net_m: float,
    turbine_key: str,
    elevation_m: float = 0.0,
    water_temp_C: float = 10.0,
    safety_margin: float = 0.0,
) -> float:
    """Maximum permissible suction head H_s before cavitation [m].

    Sets σ_actual = σ_critical and solves for H_s:
        H_s_max = H_atm - H_v - (σ_c + safety_margin) · H_net

    If H_s_max < 0, the runner must be SUBMERGED below tailwater by |H_s_max| m
    to avoid cavitation. Common for Kaplan turbines at high nsN.

    Args:
        safety_margin: extra Δσ above σ_critical (typical 0.05–0.1 for design).
    """
    sigma_c = thoma_sigma_critical(nsN_metric_hp, turbine_key)
    H_atm = atmospheric_pressure_head(elevation_m)
    H_v = vapor_pressure_head(water_temp_C)
    return H_atm - H_v - (sigma_c + safety_margin) * H_net_m


# ============================================================
# TURBINE APPLICABILITY
# ============================================================

def filter_applicable_turbines(
    H: float,
    Q_design: float,
    catalog: dict[str, TurbineType] | None = None,
) -> dict[str, TurbineType]:
    """Filter turbine types applicable for given head and design flow.

    Checks that H falls within the turbine's H_range AND that the per-unit
    design flow does not exceed the technology envelope Q_max.

    Args:
        H: design head [m]
        Q_design: design flow PER UNIT [m³/s]
        catalog: turbine catalog (default: TURBINE_CATALOG)

    Returns:
        Dict of applicable TurbineType entries
    """
    if catalog is None:
        catalog = TURBINE_CATALOG
    result = {}
    for name, ttype in catalog.items():
        H_min, H_max = ttype.H_range
        if H_min <= H <= H_max and Q_design <= ttype.Q_max:
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

    Strategy: use the **minimum** number of turbines that can pass the available
    flow without exceeding Q_design per unit. This loads each running turbine as
    close to its design point as possible (best efficiency).

        n_active = clip( ceil(Q / Q_design), 1, n_turbines )
        Q_per    = min( Q / n_active, Q_design )

    Excess flow (Q > n_turbines · Q_design) is spilled.

    If sharing the flow among n_active units would drop each below Q_min
    (possible just above a switching point for types with high Q_ratio_min,
    e.g. propeller at Q ≈ 1.2·Q_design with 2 units → 0.6·Q_design each),
    the dispatch falls back to FEWER units running at Q_design and spills
    the excess, instead of shutting the whole plant down.
    Only when even a single turbine cannot reach Q_min does the plant stop.

    Args:
        Q_available: available flow [m³/s] (array, shape (n_days,))
        Q_design: design flow per turbine [m³/s]
        n_turbines: number of installed turbines
        turbine_type: TurbineType (for Q_ratio_min)

    Returns:
        (Q_per_turbine, n_active):
            Q_per_turbine — flow through each active turbine [m³/s], shape (n_days,)
            n_active — number of active turbines per day (0..n_turbines), shape (n_days,)
    """
    Q = np.asarray(Q_available, dtype=float)
    # Treat NaN/inf as no flow available — avoids ceil() raising on weird inputs
    Q = np.where(np.isfinite(Q), Q, 0.0)
    Q_min = turbine_type.Q_ratio_min * Q_design

    # Minimum n_active so each turbine sees ≤ Q_design (use more turbines for high flow)
    n_needed = np.ceil(np.maximum(Q, 0) / Q_design).astype(int)
    n_active = np.clip(n_needed, 1, n_turbines)
    Q_per = np.minimum(Q / np.maximum(n_active, 1), Q_design)

    # Fallback: if sharing among n_active drops each unit below Q_min while
    # Q itself is at least one unit's Q_design, run fewer units at Q_design
    # and spill the excess rather than shutting the plant down.
    fallback = (Q_per < Q_min) & (Q >= Q_design)
    if np.any(fallback):
        n_fb = np.clip(np.floor(Q / Q_design).astype(int), 1, n_turbines)
        n_active = np.where(fallback, n_fb, n_active)
        Q_per = np.where(fallback, np.minimum(Q / np.maximum(n_fb, 1), Q_design), Q_per)

    # Shut down where each turbine would be below Q_min, or Q ≤ 0
    shutdown = (Q_per < Q_min) | (Q <= 0)
    n_active = np.where(shutdown, 0, n_active)
    Q_per = np.where(shutdown, 0.0, Q_per)

    return Q_per, n_active

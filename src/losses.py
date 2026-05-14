"""
Hydraulic Losses Module
========================
Models for head losses in hydropower waterway components.

Each loss function returns head loss ΔH [m] for given flow Q [m³/s].
Functions are designed to be composed via total_head_loss().

Loss components:
- Trash rack (inlet screen)
- Pipe friction (Darcy-Weisbach)
- Minor losses (bends, contractions, expansions, valves)
- Spiral casing (turbine inlet)
- Draft tube (turbine outlet)

Reference: Czekalski (2008), ESHA Guide (2004), Penche (2004)
"""

import numpy as np
from typing import Callable


# ============================================================
# CONSTANTS
# ============================================================

G = 9.81  # gravitational acceleration [m/s²]


# ============================================================
# HELPER: velocity from flow and area
# ============================================================

def _velocity(Q: np.ndarray, A: float) -> np.ndarray:
    """Flow velocity v = Q / A [m/s]."""
    return np.asarray(Q) / A


def _velocity_head(Q: np.ndarray, A: float) -> np.ndarray:
    """Velocity head v²/(2g) [m]."""
    v = _velocity(Q, A)
    return v ** 2 / (2 * G)


# ============================================================
# TRASH RACK LOSSES
# ============================================================

def trash_rack_loss(
    Q: np.ndarray,
    A_rack: float,
    bar_width: float = 0.01,
    bar_spacing: float = 0.05,
    bar_shape_coeff: float = 2.42,
    angle_deg: float = 90.0,
) -> np.ndarray:
    """Head loss through trash rack (krata wlotowa).

    Kirschmer formula:
        ΔH = β * (s/b)^(4/3) * sin(α) * v²/(2g)

    where:
        β — bar shape coefficient (2.42 for rectangular, 1.79 for circular,
            1.67 for streamlined)
        s — bar width [m]
        b — bar spacing (clear opening) [m]
        α — rack angle to horizontal [deg] (90° = vertical)
        v — approach velocity at rack [m/s]

    Args:
        Q: flow [m³/s] (scalar or array)
        A_rack: total rack area (gross) [m²]
        bar_width: bar thickness s [m]
        bar_spacing: clear spacing between bars b [m]
        bar_shape_coeff: β coefficient (default 2.42 for rectangular bars)
        angle_deg: rack inclination angle [deg] (90 = vertical)

    Returns:
        Head loss ΔH [m]
    """
    Q = np.asarray(Q, dtype=float)
    sin_alpha = np.sin(np.radians(angle_deg))
    xi = bar_shape_coeff * (bar_width / bar_spacing) ** (4 / 3) * sin_alpha
    return xi * _velocity_head(Q, A_rack)


# ============================================================
# PIPE FRICTION LOSSES (Darcy-Weisbach)
# ============================================================

def _colebrook_f(Re: np.ndarray, k_s: float, D: float) -> np.ndarray:
    """Darcy friction factor — Swamee-Jain explicit approximation of Colebrook-White.

        f = 0.25 / [log10(k_s/(3.7·D) + 5.74/Re^0.9)]²

    Valid for 5e3 ≤ Re ≤ 1e8 and 1e-6 ≤ k_s/D ≤ 1e-2 (well above
    laminar; covers all turbulent pipe-flow regimes in small hydro).
    """
    Re = np.maximum(Re, 1.0)  # avoid log(0)
    term = k_s / (3.7 * D) + 5.74 / Re ** 0.9
    return 0.25 / np.log10(term) ** 2


def pipe_friction_loss(
    Q: np.ndarray,
    D: float,
    L: float,
    k_s: float = 0.001,
    nu: float = 1.0e-6,
) -> np.ndarray:
    """Head loss due to pipe friction (Darcy-Weisbach).

    ΔH = f * (L/D) * v²/(2g)

    where f is the Darcy friction factor (Swamee-Jain approximation).

    Args:
        Q: flow [m³/s]
        D: pipe inner diameter [m]
        L: pipe length [m]
        k_s: absolute roughness [m] (default 1mm = steel pipe)
        nu: kinematic viscosity [m²/s] (default 1e-6 for water at ~20°C)

    Returns:
        Head loss ΔH [m]
    """
    Q = np.asarray(Q, dtype=float)
    A = np.pi * D ** 2 / 4
    v = _velocity(Q, A)
    Re = np.abs(v) * D / nu
    f = _colebrook_f(Re, k_s, D)
    return f * (L / D) * _velocity_head(Q, A)


# ============================================================
# MINOR LOSSES (bends, contractions, expansions, valves)
# ============================================================

def minor_loss(
    Q: np.ndarray,
    A: float,
    xi: float,
) -> np.ndarray:
    """Generic minor (local) head loss.

    ΔH = ξ * v²/(2g)

    Common ξ values:
        - Sharp-edged inlet: 0.5
        - Rounded inlet: 0.1-0.2
        - 90° bend (r/D=1): 0.5-1.0
        - 90° bend (r/D=3): 0.2-0.3
        - Gate valve (fully open): 0.1-0.2
        - Butterfly valve (fully open): 0.2-0.5
        - Sudden expansion: (1 - A1/A2)²
        - Sudden contraction: 0.5 * (1 - A2/A1)
        - Pipe exit: 1.0

    Args:
        Q: flow [m³/s]
        A: reference cross-section area [m²]
        xi: loss coefficient [-]

    Returns:
        Head loss ΔH [m]
    """
    Q = np.asarray(Q, dtype=float)
    return xi * _velocity_head(Q, A)


# Note: spiral casing and draft tube losses are also "minor losses" —
# they use the same formula ΔH = ξ · v²/(2g) with context-specific ξ.
# Call minor_loss(Q, A_inlet, xi) directly with appropriate ξ:
#   - spiral casing: ξ ≈ 0.05–0.20 (well-designed → simple volute)
#   - draft tube: ξ ≈ 0.15–0.40 (referenced to inlet velocity; a draft
#     tube recovers kinetic energy by decelerating flow — without it,
#     the exit loss would be ξ = 1.0 on the runner-exit velocity).


# ============================================================
# COMBINERS
# ============================================================

def total_head_loss(
    Q: np.ndarray,
    loss_components: list[Callable],
) -> np.ndarray:
    """Sum head losses from multiple components.

    Each component in loss_components is a callable that takes Q [m³/s]
    and returns ΔH [m]. Students build the list by selecting which
    components apply to their WPP configuration.

    Example:
        loss_fns = [
            lambda Q: trash_rack_loss(Q, A_rack=3.0),
            lambda Q: pipe_friction_loss(Q, D=1.5, L=50),
            lambda Q: minor_loss(Q, A=1.77, xi=0.3),  # bend
            lambda Q: draft_tube_loss(Q, A_inlet=1.0, A_outlet=3.0),
        ]
        dH = total_head_loss(Q_sorted, loss_fns)

    Args:
        Q: flow [m³/s] (array)
        loss_components: list of callables Q → ΔH

    Returns:
        Total head loss ΔH [m] (array, same shape as Q)
    """
    Q = np.asarray(Q, dtype=float)
    total = np.zeros_like(Q)
    for fn in loss_components:
        total += fn(Q)
    return total


def net_head(
    H_gross: np.ndarray,
    Q: np.ndarray,
    loss_components: list[Callable],
) -> np.ndarray:
    """Net head after subtracting hydraulic losses.

    H_net = H_gross - ΔH_total

    Clipped to >= 0 (negative head is physically impossible).

    Args:
        H_gross: gross head [m] (scalar or array)
        Q: flow [m³/s] (array)
        loss_components: list of loss functions (see total_head_loss)

    Returns:
        Net head H_net [m] (array)
    """
    dH = total_head_loss(Q, loss_components)
    return np.maximum(np.asarray(H_gross) - dH, 0.0)

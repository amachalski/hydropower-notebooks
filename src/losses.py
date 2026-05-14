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
    """Darcy friction factor from Colebrook-White equation (iterative).

    Swamee-Jain explicit approximation:
        f = 0.25 / [log10(k_s/(3.7*D) + 5.74/Re^0.9)]^2
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


# ============================================================
# SPIRAL CASING LOSSES
# ============================================================

def spiral_casing_loss(
    Q: np.ndarray,
    A_inlet: float,
    xi: float = 0.1,
) -> np.ndarray:
    """Head loss in spiral (volute) casing.

    ΔH = ξ * v²/(2g)

    Typical ξ values:
        - Well-designed spiral casing: 0.05-0.10
        - Simple volute: 0.10-0.20

    Args:
        Q: flow [m³/s]
        A_inlet: spiral casing inlet area [m²]
        xi: loss coefficient (default 0.1)

    Returns:
        Head loss ΔH [m]
    """
    return minor_loss(Q, A_inlet, xi)


# ============================================================
# DRAFT TUBE LOSSES
# ============================================================

def draft_tube_loss(
    Q: np.ndarray,
    A_inlet: float,
    A_outlet: float,
    xi: float = 0.3,
) -> np.ndarray:
    """Head loss in draft tube (rura ssawna).

    The draft tube recovers kinetic energy by decelerating flow.
    Loss is referenced to inlet velocity:

    ΔH = ξ * v_inlet²/(2g)

    where ξ accounts for friction and imperfect diffusion.

    Typical ξ values:
        - Straight conical tube: 0.15-0.25
        - Elbow draft tube: 0.25-0.40
        - Simple pipe exit: 0.5-1.0

    The net effect of a draft tube is usually beneficial
    (without it, ξ_exit = 1.0 based on runner exit velocity).

    Args:
        Q: flow [m³/s]
        A_inlet: draft tube inlet area (≈ runner exit area) [m²]
        A_outlet: draft tube outlet area [m²]
        xi: loss coefficient referenced to inlet velocity (default 0.3)

    Returns:
        Head loss ΔH [m]
    """
    return minor_loss(Q, A_inlet, xi)


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

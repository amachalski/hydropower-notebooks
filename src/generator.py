"""
Generator & Electrical Losses Module
======================================
Models for generator efficiency, transformer losses, and auxiliary power.

Generator efficiency model:
    eta_g = P / (P + P_loss)
    P_loss = P_cu + P_fe + P_mech
           = k_cu * (P/P_n)^2 * P_n + k_fe * P_n + k_mech * P_n

    where:
        P_cu  — copper losses (proportional to load^2)
        P_fe  — iron/core losses (constant, independent of load)
        P_mech — mechanical losses (friction, windage, constant)

Reference: Kovalev (1986), IEEE Std 115, IEC 60034
"""

import numpy as np


# ============================================================
# GENERATOR EFFICIENCY
# ============================================================

def generator_efficiency(
    P_ratio: np.ndarray,
    k_cu: float = 0.025,
    k_fe: float = 0.010,
    k_mech: float = 0.005,
) -> np.ndarray:
    """Generator efficiency as function of relative load P/P_rated.

    Model:
        eta_g = P / (P + P_cu + P_fe + P_mech)

    where (expressed as fractions of P_rated):
        P_cu   = k_cu * (P/Pn)^2    — copper losses (load-dependent, ~I^2*R)
        P_fe   = k_fe               — iron losses (constant, hysteresis + eddy)
        P_mech = k_mech             — mechanical losses (bearings, windage)

    Typical loss coefficients for small hydro generators:
        k_cu:   0.015-0.035  (copper/winding losses)
        k_fe:   0.005-0.015  (iron/core losses)
        k_mech: 0.003-0.008  (mechanical losses)

    At full load (P_ratio=1.0):
        eta_g = 1 / (1 + k_cu + k_fe + k_mech)

    Example: k_cu=0.025, k_fe=0.010, k_mech=0.005 → eta_g(1.0) = 0.961

    Args:
        P_ratio: P / P_rated [-] (scalar or array, 0..1+)
        k_cu: copper loss coefficient [-]
        k_fe: iron loss coefficient [-]
        k_mech: mechanical loss coefficient [-]

    Returns:
        Efficiency eta_g [-] (0 where P_ratio <= 0)
    """
    P_ratio = np.asarray(P_ratio, dtype=float)

    # Loss components (as fraction of P_rated)
    loss_cu = k_cu * P_ratio ** 2      # quadratic with load
    loss_fe = k_fe                      # constant
    loss_mech = k_mech                  # constant
    total_loss = loss_cu + loss_fe + loss_mech

    # Efficiency: eta = P / (P + losses), all in P/Pn units
    eta = np.where(
        P_ratio > 0,
        P_ratio / (P_ratio + total_loss),
        0.0,
    )
    return np.clip(eta, 0.0, 1.0)


def generator_efficiency_peak(
    k_cu: float = 0.025,
    k_fe: float = 0.010,
    k_mech: float = 0.005,
) -> tuple[float, float]:
    """Find the load ratio at which generator efficiency peaks.

    Peak occurs when variable losses equal fixed losses:
        k_cu * P_ratio^2 = k_fe + k_mech
        P_ratio_opt = sqrt((k_fe + k_mech) / k_cu)

    Returns:
        (P_ratio_opt, eta_max)
    """
    k_fixed = k_fe + k_mech
    P_opt = np.sqrt(k_fixed / k_cu)
    eta_max = float(generator_efficiency(P_opt, k_cu, k_fe, k_mech))
    return float(P_opt), eta_max


# Note: transformer losses and auxiliary power follow the same structure as
# the generator (copper + iron + fixed/proportional). They are demonstrated
# inline in notebook 08 as didactic "additional refinements" — kept out of
# the module to keep the core abstraction (generator η) focused.

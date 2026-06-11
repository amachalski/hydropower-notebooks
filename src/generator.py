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

Reference: Kovalev (1986), IEEE Std 115, IEC 60034-30-1 (efficiency classes).

The default coefficients (0.025 / 0.010 / 0.005) are mid-range for a ~500 kW
machine (η_peak ≈ 0.961 ≈ IEC IE3). Real losses scale with machine size:
small machines have proportionally larger losses, large ones smaller — use
`generator_loss_coefs_for_size()` to pick coefficients matched to your P_rated.
"""

import numpy as np


# ============================================================
# GENERATOR EFFICIENCY
# ============================================================

def generator_loss_coefs_for_size(P_rated_kW: float) -> dict:
    """Suggested loss coefficients scaled by generator size.

    Empirical log-linear scaling matching IEC 60034-30-1 efficiency classes
    for synchronous machines (small hydro). Anchor points:
        ~50 kW:   k_cu ≈ 0.040, k_fe ≈ 0.015, k_mech ≈ 0.008  (η_full ≈ 0.94)
        ~500 kW:  k_cu ≈ 0.025, k_fe ≈ 0.010, k_mech ≈ 0.005  (η_full ≈ 0.96)
        ~5 MW:    k_cu ≈ 0.015, k_fe ≈ 0.005, k_mech ≈ 0.002  (η_full ≈ 0.978)

    Clamped to [50 kW, 5 MW]; outside this range coefficients are pinned.

    Returns:
        dict with keys k_cu, k_fe, k_mech — pass as **kwargs to generator_efficiency.
    """
    P = max(50.0, min(float(P_rated_kW), 5000.0))
    t = (np.log10(P) - np.log10(50)) / (np.log10(5000) - np.log10(50))
    return {
        "k_cu":   0.040 + t * (0.015 - 0.040),
        "k_fe":   0.015 + t * (0.005 - 0.015),
        "k_mech": 0.008 + t * (0.002 - 0.008),
    }


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

    Typical loss coefficients (size-dependent — see `generator_loss_coefs_for_size`):
        Small (~50 kW):  k_cu≈0.040, k_fe≈0.015, k_mech≈0.008
        Medium (~500 kW, **default**): 0.025 / 0.010 / 0.005
        Large (~5 MW):   k_cu≈0.015, k_fe≈0.005, k_mech≈0.002

    At full load (P_ratio=1.0):
        eta_g = 1 / (1 + k_cu + k_fe + k_mech)

    Example: defaults → eta_g(1.0) = 0.961 (peak at P/Pn ≈ 0.77, eta ≈ 0.963).

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

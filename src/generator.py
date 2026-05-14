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


# ============================================================
# TRANSFORMER LOSSES
# ============================================================

def transformer_efficiency(
    P_ratio: np.ndarray,
    k_cu: float = 0.010,
    k_fe: float = 0.005,
) -> np.ndarray:
    """Transformer efficiency as function of relative load.

    Same structure as generator: copper losses (load^2) + iron losses (constant).

    Typical small hydro transformer:
        k_cu: 0.008-0.015
        k_fe: 0.003-0.008

    At full load: eta_tr ≈ 0.985

    Args:
        P_ratio: P / P_rated [-]
        k_cu: copper loss coefficient [-]
        k_fe: iron loss coefficient [-]

    Returns:
        Efficiency eta_tr [-]
    """
    P_ratio = np.asarray(P_ratio, dtype=float)
    loss = k_cu * P_ratio ** 2 + k_fe
    eta = np.where(P_ratio > 0, P_ratio / (P_ratio + loss), 0.0)
    return np.clip(eta, 0.0, 1.0)


# ============================================================
# AUXILIARY POWER
# ============================================================

def auxiliary_power(
    P_rated_kW: float,
    aux_fraction: float = 0.02,
    aux_fixed_kW: float = 5.0,
) -> float:
    """Auxiliary power consumption (potrzeby wlasne).

    P_aux = aux_fixed + aux_fraction * P_rated

    Covers: control systems, cooling, lighting, oil pumps, crane, etc.

    Typical values:
        aux_fraction: 0.01-0.03 (1-3% of rated power)
        aux_fixed:    2-10 kW (minimum load regardless of size)

    Args:
        P_rated_kW: rated power [kW]
        aux_fraction: variable auxiliary fraction [-]
        aux_fixed_kW: fixed auxiliary consumption [kW]

    Returns:
        Auxiliary power P_aux [kW]
    """
    return aux_fixed_kW + aux_fraction * P_rated_kW


# ============================================================
# COMBINED ELECTRICAL EFFICIENCY
# ============================================================

def electrical_efficiency(
    P_ratio: np.ndarray,
    gen_k_cu: float = 0.025,
    gen_k_fe: float = 0.010,
    gen_k_mech: float = 0.005,
    trafo_k_cu: float = 0.010,
    trafo_k_fe: float = 0.005,
    include_trafo: bool = True,
) -> np.ndarray:
    """Combined electrical efficiency (generator + optional transformer).

    eta_elec = eta_generator * eta_transformer

    Args:
        P_ratio: P / P_rated [-]
        gen_k_cu, gen_k_fe, gen_k_mech: generator loss coefficients
        trafo_k_cu, trafo_k_fe: transformer loss coefficients
        include_trafo: whether to include transformer losses

    Returns:
        Combined electrical efficiency [-]
    """
    eta_g = generator_efficiency(P_ratio, gen_k_cu, gen_k_fe, gen_k_mech)
    if include_trafo:
        eta_t = transformer_efficiency(P_ratio, trafo_k_cu, trafo_k_fe)
        return eta_g * eta_t
    return eta_g

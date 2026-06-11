"""
Financial Estimation Module
=============================
Cost models for hydropower plant investment, O&M, revenue, and economic metrics.

Electromechanical equipment cost: Ogayar & Vidal (2009) formula, inflation-adjusted.
Civil works and other costs: percentage-based breakdown from IRENA (2012, 2023).

References:
    [1] Ogayar B., Vidal P.G. (2009) "Cost determination of the electro-mechanical
        equipment of a small hydro-power plant." Renewable Energy 34(1):6-13.
        doi:10.1016/j.renene.2008.04.039
    [2] IRENA (2012) "Renewable Energy Technologies: Cost Analysis Series —
        Hydropower." Working Paper, Vol.1 Power Sector, Issue 3/5.
    [3] IRENA (2024) "Renewable Power Generation Costs in 2023."
        ISBN 978-92-9260-587-2.
    [4] NREL (2024) "Annual Technology Baseline — Hydropower."
        atb.nrel.gov/electricity/2024/hydropower
    [5] IEA (2021) "Hydropower Special Market Report."
"""

import numpy as np
from dataclasses import dataclass


# ============================================================
# ELECTROMECHANICAL EQUIPMENT COST
# ============================================================

# Ogayar & Vidal (2009) coefficients: C_em = a * P^b * H^c  [EUR_2009]
# P in kW, H in m, C_em in EUR (2009 price level)
# Source: Table 3 in Ogayar & Vidal (2009), Renewable Energy 34(1):6-13
#
# Turbine type      a          b        c        R²     Valid range
# Pelton         17693     -0.3644  -0.2810   0.94    P<2MW, H>50m
# Francis        25698     -0.5600  -0.1270   0.85    P<2MW, H>10m
# Kaplan         33236     -0.5800  -0.1130   0.87    P<2MW, H<20m
# Semi-Kaplan    19498     -0.5800  -0.1130   0.87    P<2MW, H<20m

_OGAYAR_COEFFS = {
    "pelton":      {"a": 17693, "b": -0.3644, "c": -0.2810},
    "francis":     {"a": 25698, "b": -0.5600, "c": -0.1270},
    "kaplan":      {"a": 33236, "b": -0.5800, "c": -0.1130},
    "semi_kaplan": {"a": 19498, "b": -0.5800, "c": -0.1130},
}

# Inflation adjustment from 2009 to 2024 price level
# Based on Eurostat HICP (Harmonised Index of Consumer Prices) for EU
# 2009=100, 2024≈137 → factor ≈ 1.37
# Source: Eurostat [prc_hicp_aind], EU-27 aggregate, all items
INFLATION_2009_TO_2024 = 1.37

# EUR/PLN exchange rate used throughout the course
# (NBP średni 2024 ≈ 4.30–4.35; round 4.6 chosen for didactic
# consistency with WPE_2.xlsm and notebook 05 unit costs).
EUR_PLN_RATE = 4.6


def eur_to_pln(eur: float, rate: float = EUR_PLN_RATE) -> float:
    """Convert EUR amount to PLN at fixed didactic rate."""
    return eur * rate


def electromechanical_cost(
    P_kW: float,
    H: float,
    turbine_type: str = "kaplan",
    inflation_factor: float = INFLATION_2009_TO_2024,
) -> float:
    """Electromechanical equipment cost (turbine + generator + regulator).

    Ogayar & Vidal (2009) formula, adjusted for inflation:

        C_em = inflation * a * P^b * H^c    [EUR/kW]

    Then total:  C_em_total = C_em_per_kW * P_kW    [EUR]

    Valid for P < 2 MW. Extrapolating to larger units UNDERESTIMATES cost:
    the per-kW power law (P^b, b ≈ -0.58) keeps falling far below the
    EUR/kW observed for multi-MW plants. Treat results beyond 2 MW as a
    lower bound (actual costs are higher).

    Args:
        P_kW: installed capacity per unit [kW]
        H: net head [m]
        turbine_type: 'kaplan', 'francis', 'pelton', or 'semi_kaplan'
        inflation_factor: price level adjustment (default 2009→2024)

    Returns:
        Total electromechanical cost [EUR] for one unit
    """
    # Map turbine catalog names to Ogayar coefficient keys
    type_map = {
        "kaplan": "kaplan",
        "pl10": "kaplan",
        "pl20": "kaplan",
        "francis": "francis",
        "pelton": "pelton",
        "propeller": "semi_kaplan",
        "crossflow": "semi_kaplan",  # approximate
        "semi_kaplan": "semi_kaplan",
    }
    key = type_map.get(turbine_type, "kaplan")
    coeffs = _OGAYAR_COEFFS[key]

    if P_kW > 2000:
        import warnings
        warnings.warn(
            f"Ogayar & Vidal (2009) validated for P<2 MW; extrapolating to P={P_kW:.0f} kW. "
            f"Result biased LOW — the fitted power law keeps dropping below the EUR/kW "
            f"observed for multi-MW plants. Treat as a lower bound on cost.",
            stacklevel=2,
        )

    # C_em in EUR/kW (2009 prices)
    c_per_kw = coeffs["a"] * P_kW ** coeffs["b"] * H ** coeffs["c"]

    # Adjust for inflation
    c_per_kw *= inflation_factor

    return c_per_kw * P_kW


# ============================================================
# CIVIL WORKS COST
# ============================================================

# Civil works as fraction of electromechanical cost
# Depends on plant type and size
# Source: IRENA (2012), Table 5.1; IRENA (2023), Chapter 6
#
# Plant type                  civil/EM ratio
# Run-of-river (small <5MW):  0.8 - 1.2
# Run-of-river (large >5MW):  1.5 - 3.0
# Dam/reservoir:               2.0 - 5.0
# Existing dam (retrofit):     0.3 - 0.8

_CIVIL_RATIOS = {
    "run_of_river_small": 1.0,   # civil ≈ 1.0x electromechanical
    "run_of_river_large": 2.0,   # civil ≈ 2.0x electromechanical
    "dam_reservoir": 3.5,        # civil ≈ 3.5x electromechanical
    "existing_dam": 0.5,         # civil ≈ 0.5x electromechanical
}


def civil_works_cost(
    em_cost_eur: float,
    plant_type: str = "run_of_river_small",
    civil_ratio: float | None = None,
) -> float:
    """Civil works cost estimated as multiple of electromechanical cost.

    Civil works include: dam/weir, intake, penstock/canal, powerhouse,
    tailrace, access roads, site preparation.

    Ratios from IRENA (2012, 2023):
        run_of_river_small (<5MW): 0.8-1.2x EM cost (default 1.0x)
        run_of_river_large (>5MW): 1.5-3.0x EM cost (default 2.0x)
        dam_reservoir:             2.0-5.0x EM cost (default 3.5x)
        existing_dam (retrofit):   0.3-0.8x EM cost (default 0.5x)

    Args:
        em_cost_eur: electromechanical equipment cost [EUR]
        plant_type: one of 'run_of_river_small', 'run_of_river_large',
                    'dam_reservoir', 'existing_dam'
        civil_ratio: override ratio (if provided, plant_type is ignored)

    Returns:
        Civil works cost [EUR]
    """
    if civil_ratio is None:
        civil_ratio = _CIVIL_RATIOS.get(plant_type, 1.0)
    return em_cost_eur * civil_ratio


# ============================================================
# OTHER COST COMPONENTS
# ============================================================

def grid_connection_cost(
    P_kW: float,
    cost_per_kw: float = 100.0,
) -> float:
    """Grid connection cost.

    Source: NREL ATB 2024 uses ~$60-100/kW for grid connection.
    European values similar: EUR 50-150/kW depending on distance/voltage.

    Args:
        P_kW: total installed capacity [kW]
        cost_per_kw: cost per kW [EUR/kW] (default 100)

    Returns:
        Grid connection cost [EUR]
    """
    return cost_per_kw * P_kW


def engineering_cost(
    subtotal_eur: float,
    fraction: float = 0.10,
) -> float:
    """Engineering, design, permitting, and project management costs.

    Typically 8-15% of (EM + civil + grid) costs.
    Source: IRENA (2012), Section 5.

    Args:
        subtotal_eur: sum of EM + civil + grid costs [EUR]
        fraction: engineering cost fraction (default 0.10 = 10%)

    Returns:
        Engineering cost [EUR]
    """
    return subtotal_eur * fraction


# ============================================================
# TOTAL INVESTMENT
# ============================================================

def total_investment(
    P_kW: float,
    H: float,
    n_turbines: int = 1,
    turbine_type: str = "kaplan",
    plant_type: str = "auto",
    grid_cost_per_kw: float = 100.0,
    engineering_fraction: float = 0.10,
    inflation_factor: float = INFLATION_2009_TO_2024,
    civil_ratio: float | None = None,
) -> dict:
    """Total investment cost with full breakdown.

    Components:
        1. Electromechanical: Ogayar & Vidal (2009), inflation-adjusted
        2. Civil works: ratio × EM cost, from IRENA (2012, 2023)
        3. Grid connection: EUR/kW, from NREL ATB (2024)
        4. Engineering: % of (EM + civil + grid)

    Args:
        P_kW: installed capacity per turbine [kW]
        H: net head [m]
        n_turbines: number of identical turbines
        turbine_type: turbine type name
        plant_type: 'auto' (default — picks the IRENA run-of-river size class
                    from total capacity: <5 MW small, ≥5 MW large),
                    'run_of_river_small', 'run_of_river_large',
                    'dam_reservoir', 'existing_dam'
        grid_cost_per_kw: grid connection [EUR/kW]
        engineering_fraction: engineering cost fraction
        inflation_factor: 2009→2024 inflation
        civil_ratio: override civil/EM ratio

    Returns:
        dict with keys:
            em_eur, civil_eur, grid_eur, engineering_eur,
            total_eur, total_per_kw_eur, n_turbines, P_total_kW, plant_type
    """
    P_total = P_kW * n_turbines

    # IRENA size classes: civil/EM ratio grows for larger run-of-river plants
    if plant_type == "auto":
        plant_type = "run_of_river_small" if P_total < 5000 else "run_of_river_large"

    # Electromechanical (per unit × n_turbines)
    em_per_unit = electromechanical_cost(P_kW, H, turbine_type, inflation_factor)
    em_total = em_per_unit * n_turbines

    # Civil works
    civil = civil_works_cost(em_total, plant_type, civil_ratio)

    # Grid connection (based on total capacity)
    grid = grid_connection_cost(P_total, grid_cost_per_kw)

    # Engineering
    subtotal = em_total + civil + grid
    eng = engineering_cost(subtotal, engineering_fraction)

    total = subtotal + eng

    return {
        "em_eur": em_total,
        "civil_eur": civil,
        "grid_eur": grid,
        "engineering_eur": eng,
        "total_eur": total,
        "total_per_kw_eur": total / P_total if P_total > 0 else 0,
        "n_turbines": n_turbines,
        "P_total_kW": P_total,
        "plant_type": plant_type,
    }


# ============================================================
# O&M COSTS
# ============================================================

def annual_om_cost(
    investment_eur: float,
    om_fraction: float = 0.025,
) -> float:
    """Annual operation & maintenance cost.

    Typically 2-4% of investment for small hydro.
    Source: IRENA (2012) Section 5.3; IEA (2021) Hydropower Special Report.

    Includes: personnel, maintenance, insurance, water fees,
    spare parts, administration.

    Args:
        investment_eur: total investment [EUR]
        om_fraction: annual O&M as fraction of investment (default 2.5%)

    Returns:
        Annual O&M cost [EUR/year]
    """
    return investment_eur * om_fraction


# ============================================================
# REVENUE
# ============================================================

def annual_revenue(
    energy_mwh: float,
    energy_price_eur_mwh: float = 106.5,
) -> float:
    """Annual revenue from energy sales.

    Default price: EUR 106.5/MWh ≈ PLN 490/MWh at EUR/PLN ≈ 4.6
    (consistent with notebook 05 parameter).

    Includes: wholesale energy + green certificates / feed-in premium.
    Source: Polish URE (Energy Regulatory Office), 2024 average.

    Args:
        energy_mwh: annual energy production [MWh/year]
        energy_price_eur_mwh: energy price [EUR/MWh]

    Returns:
        Annual revenue [EUR/year]
    """
    return energy_mwh * energy_price_eur_mwh


# ============================================================
# ECONOMIC METRICS
# ============================================================

def economic_analysis(
    energy_mwh: float,
    investment_eur: float,
    energy_price_eur_mwh: float = 106.5,
    om_fraction: float = 0.025,
    discount_rate: float = 0.06,
    lifetime_years: int = 40,
) -> dict:
    """Full economic analysis: NPV, payback, LCOE, IRR.

    Args:
        energy_mwh: annual energy production [MWh/year]
        investment_eur: total investment [EUR]
        energy_price_eur_mwh: energy price [EUR/MWh]
        om_fraction: annual O&M fraction
        discount_rate: discount rate [-] (default 6%)
        lifetime_years: project lifetime [years] (default 40)

    Returns:
        dict with: annual_revenue_eur, annual_om_eur, net_annual_eur,
                   payback_years, npv_eur, lcoe_eur_mwh
    """
    rev = annual_revenue(energy_mwh, energy_price_eur_mwh)
    om = annual_om_cost(investment_eur, om_fraction)
    net = rev - om

    # Simple payback: only meaningful when net cash-flow is positive. If O&M
    # exceeds revenue (net ≤ 0) the project never pays back — return inf.
    payback = investment_eur / net if net > 0 else float("inf")

    # NPV: -I + sum(net / (1+r)^t)
    # With constant annual net: NPV = -I + net * annuity_factor
    if discount_rate > 0:
        annuity = (1 - (1 + discount_rate) ** (-lifetime_years)) / discount_rate
    else:
        annuity = lifetime_years
    npv = -investment_eur + net * annuity

    # LCOE: (I * CRF + O&M) / E
    # CRF = r * (1+r)^T / ((1+r)^T - 1)
    if discount_rate > 0:
        crf = (discount_rate * (1 + discount_rate) ** lifetime_years
               / ((1 + discount_rate) ** lifetime_years - 1))
    else:
        crf = 1.0 / lifetime_years
    lcoe = (investment_eur * crf + om) / energy_mwh if energy_mwh > 0 else float("inf")

    return {
        "annual_revenue_eur": rev,
        "annual_om_eur": om,
        "net_annual_eur": net,
        "payback_years": payback,
        "npv_eur": npv,
        "lcoe_eur_mwh": lcoe,
        "discount_rate": discount_rate,
        "lifetime_years": lifetime_years,
    }

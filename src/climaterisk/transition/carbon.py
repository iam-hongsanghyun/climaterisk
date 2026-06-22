"""Transition-risk carbon-cost passthrough.

Method (per the transition scenario):

    emissions_i      = reported Scope-1, else proxy = (value_i / 1e6) * sector_factor
    carbon_cost_i(t) = emissions_i * carbon_price(scenario, t)
    NPV_i            = Σ_t carbon_cost_i(t) / (1 + r)^(t - base_year)

Carbon prices come from the bundled NGFS trajectories (linearly interpolated to
yearly steps); sector factors are the bundled EDGAR-style intensities. All values
are treated in USD (asset values are assumed USD-equivalent for the proxy).
"""

from __future__ import annotations

from itertools import pairwise

from pydantic import BaseModel, Field

from climaterisk.core.entities import Portfolio
from climaterisk.data.libraries import load_libraries


class AssetCarbon(BaseModel):
    """Per-asset transition (carbon-cost) result."""

    id: str
    name: str
    emissions_tco2e: float
    emissions_source: str  # "reported" | "sector_proxy"
    annual_cost_by_year: dict[int, float]
    npv: float


class TransitionResult(BaseModel):
    """Portfolio transition-risk result for one NGFS scenario."""

    scenario: str
    discount_rate: float
    base_year: int
    years: list[int]
    total_cost_by_year: list[float] = Field(default_factory=list)
    total_npv: float = 0.0
    per_asset: list[AssetCarbon] = Field(default_factory=list)
    method: str = ""
    detail: str | None = None


def _interpolate(points: dict[int, float], year: int) -> float:
    """Linear interpolation of a {year: price} series, clamped at the ends."""
    years = sorted(points)
    if year <= years[0]:
        return points[years[0]]
    if year >= years[-1]:
        return points[years[-1]]
    for lo, hi in pairwise(years):
        if lo <= year <= hi:
            frac = (year - lo) / (hi - lo)
            return points[lo] + frac * (points[hi] - points[lo])
    return points[years[-1]]


def compute_transition_risk(portfolio: Portfolio) -> TransitionResult:
    """Compute the portfolio's carbon-cost trajectory and NPV under its NGFS scenario."""
    libraries = load_libraries()
    scenario = portfolio.scenario.transition
    discount_rate = portfolio.run_config.discount_rate

    price_table = libraries["carbon_prices"]["prices"]
    if scenario not in price_table:
        return TransitionResult(
            scenario=scenario,
            discount_rate=discount_rate,
            base_year=0,
            years=[],
            detail=f"no carbon-price trajectory for scenario '{scenario}'",
        )
    points = {int(y): float(p) for y, p in price_table[scenario].items()}
    base_year = min(points)
    end_year = max(points)
    years = list(range(base_year, end_year + 1))

    factors = {
        s["id"]: float(s["emission_intensity_tco2e_per_musd"])
        for s in libraries["sectors"]["sectors"]
    }

    per_asset: list[AssetCarbon] = []
    total_by_year = [0.0 for _ in years]
    total_npv = 0.0
    for asset in portfolio.assets:
        if asset.annual_emissions_tco2e is not None:
            emissions = asset.annual_emissions_tco2e
            source = "reported"
        else:
            emissions = (asset.value / 1_000_000.0) * factors.get(asset.sector, 0.0)
            source = "sector_proxy"

        annual_cost: dict[int, float] = {}
        npv = 0.0
        for i, year in enumerate(years):
            cost = emissions * _interpolate(points, year)
            annual_cost[year] = cost
            total_by_year[i] += cost
            npv += cost / ((1.0 + discount_rate) ** (year - base_year))
        total_npv += npv
        per_asset.append(
            AssetCarbon(
                id=asset.id,
                name=asset.name,
                emissions_tco2e=emissions,
                emissions_source=source,
                annual_cost_by_year=annual_cost,
                npv=npv,
            )
        )

    return TransitionResult(
        scenario=scenario,
        discount_rate=discount_rate,
        base_year=base_year,
        years=years,
        total_cost_by_year=total_by_year,
        total_npv=total_npv,
        per_asset=per_asset,
        method=(
            "Carbon-cost passthrough: emissions × NGFS shadow carbon price, "
            f"NPV discounted at {discount_rate:.1%}. Emissions reported where given, "
            "else proxied from sector intensity."
        ),
    )

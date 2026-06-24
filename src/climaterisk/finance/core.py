"""Climate-risk financial model — cashflow → NPV/IRR/DSCR → credit rating → CRP.

Pure functions (no I/O, no CLIMADA). The reference grids (DSCR→rating, rating→spread)
and financing defaults are passed in from ``finance_reference.json`` so every number is
citable and overridable. The Climate Risk Premium (CRP) is a *counterfactual*: the rise in
credit spread (and WACC) from the no-climate baseline cashflow to the climate-stressed one.

Algorithm (annual, constant-EBITDA project — the standard project-finance skeleton):
    NPV   = Σ_{t=1..N} EBITDA / (1+wacc)^t  −  CAPEX
    DSCR  = CFADS / annual_debt_service,  annual_debt_service = annuity(debt, r_d, tenor)
    rating(DSCR) via the threshold grid; spread(rating) via the spread table.
    CRP_bps = spread(stressed) − spread(baseline)         [structural, rating-driven]
    A climate-stressed run reduces annual EBITDA by the expected annual climate loss
    (physical AAI + transition carbon cost).
ASCII: discount EBITDA at WACC minus capex; debt-service coverage sets the rating; the
premium is the extra spread the climate cashflow shock costs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class FinancialProfile:
    """Project economics for one entity (portfolio-level default or a per-asset override)."""

    capex: float  # total capital outlay (currency)
    annual_ebitda: float  # baseline annual operating cashflow before climate loss
    horizon_years: int = 25
    debt_fraction: float = 0.70
    debt_tenor_years: int = 18
    risk_free_rate: float = 0.03
    baseline_spread_bps: float = 150.0  # no-climate credit spread (cost of debt over rf)
    baseline_equity_rate: float = 0.12


@dataclass
class FinanceOutcome:
    """NPV/IRR/DSCR/rating/spread for one cashflow scenario (baseline or stressed)."""

    npv: float
    irr: float | None
    min_dscr: float
    rating: str
    spread_bps: float
    wacc: float


def annuity_payment(principal: float, rate: float, n: int) -> float:
    """Level annual payment that amortises ``principal`` over ``n`` years at ``rate``."""
    if n <= 0:
        return 0.0
    if rate <= 0:
        return principal / n
    return principal * rate / (1.0 - (1.0 + rate) ** (-n))


def npv(rate: float, cashflows: list[float]) -> float:
    """NPV of ``cashflows`` (t=0,1,2,…) discounted at ``rate`` (cashflows[0] is t=0)."""
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def irr(cashflows: list[float], lo: float = -0.95, hi: float = 1.0) -> float | None:
    """Internal rate of return via bisection on NPV sign; None if no sign change in range."""
    f_lo, f_hi = npv(lo, cashflows), npv(hi, cashflows)
    if f_lo == 0:
        return lo
    if f_lo * f_hi > 0:
        return None  # no root bracketed (e.g. all-negative cashflows)
    for _ in range(100):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid, cashflows)
        if abs(f_mid) < 1e-6:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def rating_from_dscr(dscr: float, thresholds: list[dict[str, Any]]) -> str:
    """Map a DSCR to a credit rating using the descending ``rating_dscr_thresholds`` grid."""
    for entry in sorted(thresholds, key=lambda e: e["dscr_min"], reverse=True):
        if dscr >= entry["dscr_min"]:
            return str(entry["rating"])
    return str(thresholds[-1]["rating"])


def spread_from_rating(rating: str, spreads: list[dict[str, Any]]) -> float:
    """Credit spread (bps) for a rating from the ``rating_spreads_bps`` table."""
    table = {row["rating"]: float(row["spread_bps"]) for row in spreads}
    return table.get(rating, 250.0)


def _scenario(p: FinancialProfile, annual_ebitda: float, ref: dict[str, Any]) -> FinanceOutcome:
    """NPV/IRR/DSCR/rating/spread for one EBITDA level (baseline or climate-stressed)."""
    debt = p.capex * p.debt_fraction
    equity = p.capex - debt
    debt_rate = p.risk_free_rate + p.baseline_spread_bps / 1e4
    wacc = (
        (debt / p.capex) * debt_rate + (equity / p.capex) * p.baseline_equity_rate
        if p.capex > 0
        else p.baseline_equity_rate
    )
    cashflows = [-p.capex] + [annual_ebitda] * p.horizon_years
    debt_service = annuity_payment(debt, debt_rate, p.debt_tenor_years)
    min_dscr = (annual_ebitda / debt_service) if debt_service > 0 else float("inf")
    rating = rating_from_dscr(min_dscr, ref["rating_dscr_thresholds"])
    spread = spread_from_rating(rating, ref["rating_spreads_bps"])
    return FinanceOutcome(
        npv=npv(wacc, cashflows),
        irr=irr(cashflows),
        min_dscr=min_dscr,
        rating=rating,
        spread_bps=spread,
        wacc=wacc,
    )


def assess_ebitda(
    profile: FinancialProfile,
    baseline_ebitda: float,
    stressed_ebitda: float,
    ref: dict[str, Any],
) -> dict[str, Any]:
    """Assess from an explicit (baseline, stressed) EBITDA pair → NPV/IRR/DSCR/rating + CRP.

    This is the sector-agnostic engine: an asset financial model (see
    :mod:`climaterisk.finance.models`) decides how the two EBITDA levels are produced, and
    this runs the same cashflow → rating → spread chain on each.

    Args:
        profile: the project's financial profile (capex, debt, financing terms).
        baseline_ebitda: no-climate-stress annual EBITDA.
        stressed_ebitda: climate-stressed annual EBITDA (≤ baseline).
        ref: the ``finance_reference`` library (rating grid + spread table).

    Returns a dict with baseline/stressed outcomes, the NPV loss, and the CRP in bps.
    """
    baseline = _scenario(profile, baseline_ebitda, ref)
    stressed = _scenario(profile, stressed_ebitda, ref)
    crp_bps = stressed.spread_bps - baseline.spread_bps  # counterfactual climate premium
    npv_loss = baseline.npv - stressed.npv
    return {
        "baseline": asdict(baseline),
        "stressed": asdict(stressed),
        "annual_climate_loss": float(baseline_ebitda - stressed_ebitda),
        "npv_loss": float(npv_loss),
        "npv_loss_pct_capex": float(npv_loss / profile.capex * 100.0) if profile.capex > 0 else 0.0,
        "crp_bps": float(crp_bps),
        "downgrade": baseline.rating != stressed.rating,
    }


def assess(
    profile: FinancialProfile, annual_climate_loss: float, ref: dict[str, Any]
) -> dict[str, Any]:
    """Generic assessment: stressed EBITDA = baseline − expected annual climate loss.

    Thin wrapper over :func:`assess_ebitda` for the generic (non-generation) model, where the
    climate shock (physical AAI + transition carbon cost) simply reduces a flat EBITDA.
    """
    return assess_ebitda(
        profile,
        profile.annual_ebitda,
        profile.annual_ebitda - max(0.0, annual_climate_loss),
        ref,
    )

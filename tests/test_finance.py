"""Climate-risk financial core — exact math + the CRP counterfactual (offline, hermetic)."""

from __future__ import annotations

import math

from climaterisk.data.libraries import load_libraries
from climaterisk.finance import core


def _ref() -> dict:
    return load_libraries()["finance_reference"]


def test_annuity_npv_irr_against_known_values() -> None:
    # Annuity: 1000 over 10y at 10% = 1000*0.1/(1-1.1^-10) ≈ 162.745
    assert math.isclose(core.annuity_payment(1000, 0.10, 10), 162.745, rel_tol=1e-3)
    # NPV: 110 one year out at 10% = 100
    assert math.isclose(core.npv(0.10, [0.0, 110.0]), 100.0, rel_tol=1e-9)
    # IRR: -100 now, +110 next year → 10%
    irr = core.irr([-100.0, 110.0])
    assert irr is not None and math.isclose(irr, 0.10, abs_tol=1e-3)


def test_rating_and_spread_grids() -> None:
    ref = _ref()
    th, sp = ref["rating_dscr_thresholds"], ref["rating_spreads_bps"]
    assert core.rating_from_dscr(3.0, th) == "AAA"
    assert core.rating_from_dscr(1.4, th) == "BBB"
    assert core.rating_from_dscr(0.9, th) == "CCC"
    assert core.rating_from_dscr(-1.0, th) in {"CC", "C", "D"}
    assert core.spread_from_rating("BBB", sp) == 250
    assert core.spread_from_rating("AAA", sp) == 50


def test_assess_counterfactual_crp() -> None:
    ref = _ref()
    p = core.FinancialProfile(capex=1000.0, annual_ebitda=200.0)
    # Severe climate loss (75% of EBITDA) → DSCR collapses → downgrade → positive CRP.
    severe = core.assess(p, annual_climate_loss=150.0, ref=ref)
    assert severe["baseline"]["rating"] == "AAA"
    assert severe["downgrade"] is True
    assert severe["crp_bps"] > 0
    assert severe["stressed"]["min_dscr"] < severe["baseline"]["min_dscr"]
    assert severe["npv_loss"] > 0
    # Negligible loss → same rating → zero CRP.
    mild = core.assess(p, annual_climate_loss=5.0, ref=ref)
    assert mild["crp_bps"] == 0.0 and mild["downgrade"] is False

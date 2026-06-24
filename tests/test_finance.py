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


def test_rating_methods_diverge_for_same_dscr() -> None:
    # A single DSCR rates differently under each methodology — the whole point of letting
    # the user choose: 2.3× coverage is AA under Moody's/S&P, only A for a strict lender,
    # but AAA in a lenient sponsor case.
    methods = _ref()["rating_methods"]
    dscr = 2.3
    assert core.rating_from_dscr(dscr, methods["moodys_sp"]["thresholds"]) == "AA"
    assert core.rating_from_dscr(dscr, methods["lender_conservative"]["thresholds"]) == "A"
    assert core.rating_from_dscr(dscr, methods["equity_lenient"]["thresholds"]) == "AAA"


def test_resolve_rating_method_default_named_and_custom() -> None:
    from climaterisk.core.entities import FinancialProfile, RatingThreshold
    from climaterisk.finance import service

    ref = _ref()
    # No profile → library default selection.
    assert service.selected_method_ids(None, ref) == ["moodys_sp"]
    assert service.resolve_rating_method(None, ref, "moodys_sp")["code"] == "Agency"
    # Named method resolves with its short code.
    named = service.resolve_rating_method(None, ref, "lender_conservative")
    assert named["method"] == "lender_conservative" and named["code"] == "Lender"
    # Custom grid resolves from the profile's editable thresholds.
    custom = service.resolve_rating_method(
        FinancialProfile(
            custom_rating_thresholds=[
                RatingThreshold(dscr_min=1.0, rating="AAA"),
                RatingThreshold(dscr_min=-999.0, rating="D"),
            ],
        ),
        ref,
        "custom",
    )
    assert custom["method"] == "custom"
    assert core.rating_from_dscr(1.5, custom["thresholds"]) == "AAA"
    # Unknown id falls back to the default rather than raising.
    assert service.resolve_rating_method(None, ref, "nope")["method"] == "moodys_sp"


def test_selected_method_ids_prefers_multiselect() -> None:
    from climaterisk.core.entities import FinancialProfile
    from climaterisk.finance import service

    ref = _ref()
    multi = FinancialProfile(rating_methods=["lender_conservative", "moodys_sp"])
    assert service.selected_method_ids(multi, ref) == ["lender_conservative", "moodys_sp"]
    # Single field still honored for back-compat.
    single = FinancialProfile(rating_method="equity_lenient")
    assert service.selected_method_ids(single, ref) == ["equity_lenient"]


def test_service_applies_chosen_method() -> None:
    from climaterisk.core.entities import Asset, FinancialProfile, Portfolio, RunConfig
    from climaterisk.finance import service

    a = Asset(name="A", lat=35.0, lon=139.0, sector="oil_gas", value=1e9, currency="USD")
    port = Portfolio(
        assets=[a],
        run_config=RunConfig(
            financial_profile=FinancialProfile(
                capex=2e9, annual_ebitda=3e8, rating_method="equity_lenient"
            )
        ),
    )
    run_output = {
        "results": [{"status": "ok", "peril": "tc", "per_asset": [{"id": a.id, "eai": 1e7}]}]
    }
    res = service.compute_finance(port, run_output, transition_annual_cost=0.0, ref=_ref())
    assert res["rating_method"] == "equity_lenient"
    assert res["rating_thresholds"][0]["rating"] == "AAA"
    assert len(res["methods_compared"]) == 1


def test_service_compares_multiple_methods() -> None:
    from climaterisk.core.entities import Asset, FinancialProfile, Portfolio, RunConfig
    from climaterisk.finance import service

    a = Asset(name="A", lat=35.0, lon=139.0, sector="oil_gas", value=1e9, currency="USD")
    port = Portfolio(
        assets=[a],
        run_config=RunConfig(
            financial_profile=FinancialProfile(
                capex=2e9,
                annual_ebitda=3e8,
                rating_methods=["moodys_sp", "lender_conservative", "equity_lenient"],
            )
        ),
    )
    run_output = {
        "results": [{"status": "ok", "peril": "tc", "per_asset": [{"id": a.id, "eai": 1e7}]}]
    }
    res = service.compute_finance(port, run_output, transition_annual_cost=0.0, ref=_ref())
    compared = res["methods_compared"]
    assert [m["code"] for m in compared] == ["Agency", "Lender", "Sponsor"]
    # Primary (headline) is the first selected; each entry carries a full scenario.
    assert res["rating_method"] == "moodys_sp"
    assert all("baseline" in m["scenario"] and "crp_bps" in m["scenario"] for m in compared)


def test_channel_math() -> None:
    from climaterisk.finance import channels

    # outage = freq * (1 - e^(-λ t)) * dur/8760 ; λ=0.20,t=2 → P=1-e^-0.4≈0.3297
    o = channels.outage_rate(1.0, 0.20, 2.0, 48.0)
    assert math.isclose(o, (1 - math.exp(-0.4)) * 48.0 / 8760.0, rel_tol=1e-9)
    # efficiency: 10°C above design at 0.7%/°C = 7%
    assert math.isclose(channels.efficiency_loss(25.0, 15.0, 0.007), 0.07, rel_tol=1e-9)
    # no loss below design temp
    assert channels.efficiency_loss(10.0, 15.0, 0.007) == 0.0
    # composition: 0.8 base × (1-0.1)(1-0.05) = 0.684
    cf = channels.effective_capacity_factor(0.8, dispatch_penalty=0.1, efficiency_loss=0.05)
    assert math.isclose(cf, 0.8 * 0.9 * 0.95, rel_tol=1e-9)
    # water cap binds
    assert channels.effective_capacity_factor(0.8, water_constrained_cf=0.3) == 0.3


def test_power_gen_pair_builds_ebitda_from_generation() -> None:
    from climaterisk.finance import models

    gen = models.GenerationInputs(
        capacity_mw=100.0, power_price=80.0, capacity_factor=0.5, opex_per_mwh=8.0
    )
    # baseline: 100 MW × 8760 × 0.5 = 438,000 MWh × $80 = $35.04M rev − $8/MWh opex
    no_stress = models.power_gen_pair(gen, models.ChannelMagnitudes())
    gen0 = 100.0 * 8760.0 * 0.5
    assert math.isclose(no_stress.baseline, gen0 * 80.0 - 8.0 * gen0, rel_tol=1e-9)
    # with no channels, no carbon, no AAI → stressed == baseline (clean recovery)
    assert math.isclose(no_stress.stressed, no_stress.baseline, rel_tol=1e-9)
    # dispatch + efficiency stress + carbon + AAI all reduce the stressed EBITDA
    stressed = models.power_gen_pair(
        gen,
        models.ChannelMagnitudes(dispatch_penalty=0.2, efficiency_loss=0.05),
        annual_aai=1e6,
        carbon_cost=2e6,
    )
    assert stressed.stressed < stressed.baseline
    assert stressed.breakdown["cf_effective"] < stressed.breakdown["cf_baseline"]
    assert stressed.climate_loss > 0


def test_service_power_gen_model() -> None:
    from climaterisk.core.entities import Asset, FinancialProfile, Portfolio, RunConfig
    from climaterisk.data.libraries import load_libraries
    from climaterisk.finance import service

    channels_ref = load_libraries()["finance_channels"]
    a = Asset(name="Plant", lat=35.0, lon=139.0, sector="utilities", value=1e9, currency="USD")
    port = Portfolio(
        assets=[a],
        run_config=RunConfig(
            financial_profile=FinancialProfile(
                capex=2e9,
                financial_model="power_gen",
                capacity_mw=500.0,
                power_price=90.0,
                capacity_factor=0.55,
                dispatch_penalty=0.15,
                efficiency_loss=0.03,
            )
        ),
    )
    run_output = {
        "results": [{"status": "ok", "peril": "tc", "per_asset": [{"id": a.id, "eai": 5e6}]}]
    }
    res = service.compute_finance(
        port, run_output, transition_annual_cost=1e7, ref=_ref(), channels_ref=channels_ref
    )
    assert res["financial_model"] == "power_gen"
    bd = res["portfolio_breakdown"]
    assert bd["cf_effective"] < bd["cf_baseline"]  # channels bit
    assert res["portfolio"]["crp_bps"] >= 0  # stressed cashflow ≥ as risky


def test_service_aggregates_run_and_overrides() -> None:
    from climaterisk.core.entities import Asset, FinancialProfile, Portfolio, RunConfig
    from climaterisk.finance import service

    a1 = Asset(name="A", lat=35.0, lon=139.0, sector="oil_gas", value=1e9, currency="USD")
    a2 = Asset(
        name="B",
        lat=36.0,
        lon=140.0,
        sector="oil_gas",
        value=1e9,
        currency="USD",
        financial_profile=FinancialProfile(capex=5e8, annual_ebitda=8e7),  # per-asset override
    )
    port = Portfolio(
        assets=[a1, a2],
        run_config=RunConfig(financial_profile=FinancialProfile(capex=2e9, annual_ebitda=3e8)),
    )
    run_output = {
        "results": [
            {
                "status": "ok",
                "peril": "tc",
                "per_asset": [{"id": a1.id, "eai": 1e7}, {"id": a2.id, "eai": 2e7}],
            }
        ]
    }
    res = service.compute_finance(port, run_output, transition_annual_cost=5e6, ref=_ref())
    assert res["total_physical_aai"] == 3e7  # 1e7 + 2e7 summed across the peril
    assert "crp_bps" in res["portfolio"]
    assert [a["id"] for a in res["per_asset"]] == [a2.id]  # only the overridden asset
    assert res["per_asset"][0]["annual_climate_loss"] == 2e7

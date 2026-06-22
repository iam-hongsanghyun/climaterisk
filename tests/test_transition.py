"""Tests for the transition-risk carbon-cost module."""

from __future__ import annotations

from fastapi.testclient import TestClient

from climaterisk.core.entities import Asset, Portfolio, RunConfig, Scenario
from climaterisk.data.libraries import load_libraries
from climaterisk.transition.carbon import compute_transition_risk


def test_reported_vs_proxy_emissions() -> None:
    portfolio = Portfolio(
        scenario=Scenario(transition="net_zero_2050"),
        run_config=RunConfig(discount_rate=0.05),
        assets=[
            Asset(name="reported", lat=0.0, lon=0.0, value=0.0, annual_emissions_tco2e=100_000.0),
            Asset(name="proxy", lat=0.0, lon=0.0, sector="steel", value=1_000_000.0),
        ],
    )
    result = compute_transition_risk(portfolio)

    assert result.scenario == "net_zero_2050"
    assert result.base_year == 2025
    assert result.years[0] == 2025 and result.years[-1] == 2050

    reported, proxy = result.per_asset
    assert reported.emissions_source == "reported"
    assert reported.emissions_tco2e == 100_000.0
    # First-year cost = emissions × the (real NGFS) base-year carbon price from the library.
    price_2025 = load_libraries()["carbon_prices"]["prices"]["net_zero_2050"]["2025"]
    assert reported.annual_cost_by_year[2025] == 100_000.0 * price_2025

    # steel proxy: (1e6 / 1e6) * 1800 tCO2e/MUSD = 1800 tCO2e.
    assert proxy.emissions_source == "sector_proxy"
    assert proxy.emissions_tco2e == 1800.0

    assert result.total_npv > 0
    assert len(result.total_cost_by_year) == len(result.years)


def test_transition_endpoint(client: TestClient) -> None:
    model = client.post("/api/session").json()
    sid = model["id"]
    model["assets"].append(
        {"name": "Plant", "lat": 35.0, "lon": 139.0, "sector": "utilities", "value": 2_000_000.0}
    )
    model["scenario"]["transition"] = "delayed_transition"
    client.put(f"/api/session/{sid}", json=model)

    resp = client.post(f"/api/session/{sid}/transition")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario"] == "delayed_transition"
    assert len(body["per_asset"]) == 1
    assert body["per_asset"][0]["emissions_source"] == "sector_proxy"
    assert body["total_npv"] > 0

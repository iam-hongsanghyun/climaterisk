"""Tests for the HTML report export + the engine request vulnerability resolution."""

from __future__ import annotations

from fastapi.testclient import TestClient

from climaterisk.core.entities import Asset, Portfolio
from climaterisk.engines.base import PhysicalRunRequest


def test_request_resolves_vulnerability_params() -> None:
    portfolio = Portfolio(
        assets=[
            Asset(name="resi", lat=35.0, lon=139.0, sector="real_estate"),  # default residential
            Asset(
                name="plant",
                lat=34.0,
                lon=135.0,
                sector="steel",
                vulnerability_class="infrastructure",  # explicit override
            ),
        ]
    )
    req = PhysicalRunRequest.from_portfolio(portfolio)
    resi, plant = req.assets
    assert resi.vulnerability_class == "residential"
    assert resi.tc_v_half == 70.0
    assert plant.vulnerability_class == "infrastructure"  # override wins over sector default
    assert plant.tc_v_half == 110.0
    assert len(resi.flood_mdr) == len(resi.flood_depth_m)


def test_report_download(client: TestClient) -> None:
    model = client.post("/api/session").json()
    sid = model["id"]
    model["assets"].append(
        {"name": "Plant", "lat": 35.0, "lon": 139.0, "sector": "utilities", "value": 2_000_000.0}
    )
    client.put(f"/api/session/{sid}", json=model)

    resp = client.get(f"/api/session/{sid}/report")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.text
    assert "Climate Risk Report" in body
    assert "Transition risk" in body
    assert "Plant" in body

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


def test_report_includes_new_engine_sections() -> None:
    from climaterisk.core.entities import Portfolio
    from climaterisk.report.html import build_html_report
    from climaterisk.transition.carbon import compute_transition_risk

    p = Portfolio()
    t = compute_transition_risk(p)
    html = build_html_report(
        p,
        None,
        t,
        supplychain={
            "status": "ok",
            "mriot": "WIOD16",
            "total_direct": 100.0,
            "total_indirect": 300.0,
            "by_sector": [{"sector": "Real estate", "indirect": 200.0}],
        },
        forecast={"status": "ok", "n_tracks": 5, "total_impact": 1000.0},
        calibration={
            "status": "ok",
            "country": "JPN",
            "param": "v_half",
            "initial": 84.7,
            "calibrated": 70.0,
        },
    )
    assert "Supply-chain (indirect impact)" in html
    assert "Operational forecast" in html
    assert "Impact-function calibration" in html

"""Engine regression test — pins the CLIMADA tropical-cyclone math to a captured baseline.

This is the plan's "engine unit test" (a tiny ImpactCalc against a small bundled
hazard, asserting ``aai_agg`` against a captured baseline). It runs the worker's own
helpers against the **committed local catalog** hazard (``TC rcp45 JPN 2040``), so it is
fully offline and deterministic — no CLIMADA Data API call.

Requires CLIMADA, so it is skipped in the lightweight backend env (``uv run pytest``)
and runs in the project-local worker env::

    ./.climada-env/bin/python -m pytest tests/test_physical_regression.py

Baseline captured 2026-06-23 from a 1-asset Tokyo portfolio (value $10M, real-estate
default vulnerability, Emanuel ``v_half=70``) against the local JPN TC hazard. If the
catalog hazard is rebuilt from a different Data-API snapshot, re-capture these numbers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("climada")
pytest.importorskip("scipy")

REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

# --- captured baseline (asset's currency = USD) ------------------------------------
_TOKYO = {"id": "a0", "lat": 35.6762, "lon": 139.6503, "value": 1.0e7, "currency": "USD"}
_V_HALF = 70.0  # real-estate default vulnerability class (Emanuel TC)
_BASELINE_AAI = 105426.03
_BASELINE_RP = [10.0, 25.0, 50.0, 100.0, 250.0]
_BASELINE_RP_IMPACT = [286765.2, 722886.6, 1238370.6, 1842097.4, 3101402.2]


@pytest.fixture(scope="module")
def tc_impact():  # type: ignore[no-untyped-def]
    """Run TC ImpactCalc on the local JPN hazard with the worker's own helpers."""
    from climada.entity import ImpactFuncSet
    from climada.entity.impact_funcs.trop_cyclone import ImpfTropCyclone
    from climaterisk_worker import catalog, physical

    haz = catalog.load_hazard("tropical_cyclone", "rcp45", "JPN", 2040)
    if haz is None:
        pytest.skip("local catalog hazard TC/rcp45/JPN/2040 not present")
    impf_set = ImpactFuncSet([ImpfTropCyclone.from_emanuel_usa(impf_id=1, v_half=_V_HALF)])
    exp, _ = physical._build_exposures([_TOKYO], "impf_TC", [1])
    return physical._impact(exp, impf_set, haz)


def test_aai_agg_matches_baseline(tc_impact) -> None:  # type: ignore[no-untyped-def]
    """Aggregate expected annual impact reproduces the captured baseline."""
    import numpy as np

    np.testing.assert_allclose(float(tc_impact.aai_agg), _BASELINE_AAI, rtol=1e-3)


def test_single_asset_eai_equals_aai(tc_impact) -> None:  # type: ignore[no-untyped-def]
    """For a one-asset portfolio the per-asset EAI equals the aggregate AAI."""
    import numpy as np

    eai = [float(x) for x in tc_impact.eai_exp]
    assert len(eai) == 1
    np.testing.assert_allclose(eai[0], _BASELINE_AAI, rtol=1e-3)


def test_freq_curve_matches_baseline(tc_impact) -> None:  # type: ignore[no-untyped-def]
    """The return-period exceedance curve reproduces the captured baseline."""
    import numpy as np

    fc = tc_impact.calc_freq_curve(_BASELINE_RP)
    np.testing.assert_allclose([float(x) for x in fc.return_per], _BASELINE_RP)
    np.testing.assert_allclose([float(x) for x in fc.impact], _BASELINE_RP_IMPACT, rtol=1e-3)

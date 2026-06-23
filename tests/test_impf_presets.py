"""Impact-function presets library — structural integrity (offline, hermetic).

These presets carry published values (Eberenz et al. 2021 TC v_half; Huizinga et al.
2017 JRC flood curves). The test guards the shape the studio relies on, not the exact
numbers (which ``scripts/build_impf_presets.py`` regenerates from CLIMADA).
"""

from __future__ import annotations

from itertools import pairwise

from climaterisk.data.libraries import load_libraries


def test_presets_library_loads() -> None:
    lib = load_libraries()
    assert "impf_presets" in lib
    presets = lib["impf_presets"]["presets"]
    assert len(presets) >= 10  # 11 TC regions + 6 flood continents in the shipped set


def test_tc_presets_set_positive_v_half() -> None:
    presets = load_libraries()["impf_presets"]["presets"]
    tc = [p for p in presets if p["peril"] == "tc"]
    assert tc, "expected at least one TC preset"
    for p in tc:
        assert p["id"] and p["label"] and p["provenance"]
        assert isinstance(p["tc_v_half"], (int, float)) and p["tc_v_half"] > 0


def test_flood_presets_match_depth_breakpoints_and_are_monotonic() -> None:
    lib = load_libraries()
    depths = lib["impact_functions"]["flood_depth_m"]
    flood = [p for p in lib["impf_presets"]["presets"] if p["peril"] == "flood"]
    assert flood, "expected at least one flood preset"
    for p in flood:
        mdr = p["flood_mdr"]
        assert len(mdr) == len(depths), p["id"]
        assert mdr[0] == 0.0  # no damage at zero depth
        assert all(0.0 <= v <= 1.0 for v in mdr)
        assert all(b >= a for a, b in pairwise(mdr)), f"{p['id']} not monotonic"

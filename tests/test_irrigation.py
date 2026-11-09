"""Tests for irrigated land suitability. Run: python3 -m pytest tests  (or python3 tests/test_irrigation.py)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from water_res import FactorBand, IrrigationMethod as M, assess_irrigation, reference_gross_m3_per_ha  # noqa: E402


def land(slope, depth=120, drain=4.5):
    slope = np.atleast_2d(np.array(slope, float))
    full = lambda v: np.full(slope.shape, float(v))
    return {"slope_pct": slope, "soil_depth_cm": full(depth), "drainage_class": full(drain)}


def run(slope, access="GRAVITY", depth=120, drain=4.5, available=True):
    L = land(slope, depth, drain)
    shape = L["slope_pct"].shape
    return assess_irrigation(L, np.full(shape, available), np.full(shape, access, dtype=object), cell_ha=1.0)


def test_bands_reject_unnested_limits():
    try:
        FactorBand(5, 2, 8, False)
    except ValueError:
        return
    raise AssertionError("unnested bands should raise")


def test_flat_deep_gravity_land_is_s1_except_sprinkler_which_needs_pressure():
    s = run([1.0])
    assert s.rank[M.SURFACE][0, 0] == 3 and s.rank[M.DRIP][0, 0] == 3
    assert s.rank[M.SPRINKLER][0, 0] == 2 and s.limiting[M.SPRINKLER][0, 0] == "water access"
    assert run([1.0], access="PUMPED").rank[M.SPRINKLER][0, 0] == 3


def test_slope_separates_the_methods():
    s = run([10.0])                                    # too steep for furrows, fine for drip
    assert s.rank[M.SURFACE][0, 0] == 0 and s.rank[M.SPRINKLER][0, 0] == 2 and s.rank[M.DRIP][0, 0] == 2
    assert s.limiting[M.SURFACE][0, 0] == "slope_pct"
    assert s.best_method[0, 0] == "sprinkler"          # tie between sprinkler and drip -> the cheaper one


def test_harvest_only_water_rules_out_surface_but_not_small_drip():
    s = run([1.0], access="HARVEST_ONLY")
    assert s.rank[M.SURFACE][0, 0] == 0 and s.rank[M.DRIP][0, 0] == 1
    assert s.limiting[M.SURFACE][0, 0] == "water access"


def test_poor_drainage_limits_surface_irrigation():
    s = run([1.0], drain=2.2)                          # Vertisol valley
    assert s.rank[M.SURFACE][0, 0] == 1 and s.rank[M.DRIP][0, 0] == 2


def test_unavailable_land_is_not_assessed():
    s = run([1.0], available=False)
    assert all(s.rank[m][0, 0] == -1 for m in M) and s.best_method[0, 0] == ""


def test_reference_demand_is_dry_season_only_and_drip_needs_least():
    et0, rain = np.full(12, 4.0), np.zeros(12)
    surf, drip = reference_gross_m3_per_ha(et0, rain, M.SURFACE), reference_gross_m3_per_ha(et0, rain, M.DRIP)
    assert surf[6] == 0 and surf[0] > 0                # July (rains) zero, January positive
    assert abs(surf[0] / drip[0] - 0.90 / 0.60) < 1e-9  # same crop water, drip loses less


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  [PASS] {name}")
            except Exception as e:  # debugging block: report and continue
                failed += 1; print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)

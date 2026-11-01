"""Tests for Stage 04. Run: python3 -m pytest tests  (or python3 tests/test_planner.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from crop_plan import ClusterProfile, CropOption, DemandSignal, InfeasiblePlan, PlanningPolicy, expected_yield, plan  # noqa: E402

TEFF = CropOption("teff", "teff", "meher", 110, 2.0, 100_000, 40_000)
MAIZE = CropOption("maize", "maize", "meher", 150, 5.0, 30_000, 45_000)
ONION = CropOption("onion", "onion", "dry", 150, 20.0, 18_000, 150_000, water_m3_ha=(0, 1000) + (0,) * 10)


def cluster(**kw):
    base = dict(cluster_id="X", area_ha={"meher": 100, "dry": 50}, suitability={"teff": 1.0, "maize": 1.0, "onion": 1.0},
                cycle_fit={}, water_m3=(0, 20_000) + (0,) * 10)
    base.update(kw)
    return ClusterProfile(**base)


def test_expected_yield_uses_suitability_and_cycle_fit():
    c = cluster(suitability={"maize": 0.8}, cycle_fit={"maize": 0.5})
    assert abs(expected_yield(MAIZE, c) - 5.0 * 0.8 * (0.5 + 0.5 * 0.5)) < 1e-9


def test_land_limit_respected_and_best_margin_chosen():
    p = plan([cluster()], [TEFF, MAIZE], [])
    assert abs(sum(a.hectares for a in p.allocations) - 100) < 1e-6
    assert p.hectares("X", "teff") > 99      # teff margin 160k > maize 105k


def test_demand_cap_shifts_area():
    p = plan([cluster()], [TEFF, MAIZE], [DemandSignal("teff", 0, 60)])
    assert abs(p.tonnes_by_product["teff"] - 60) < 1e-6 and p.hectares("X", "maize") > 69


def test_monthly_water_limits_irrigated_area():
    p = plan([cluster()], [ONION], [])
    assert abs(p.hectares("X", "onion") - 20) < 1e-6             # 20,000 m3 / 1,000 m3 per ha in February
    assert any(s.constraint == "water X Feb" for s in p.binding)


def test_unsuitable_option_never_planted():
    p = plan([cluster(suitability={"teff": 0.0, "maize": 1.0})], [TEFF, MAIZE], [])
    assert p.hectares("X", "teff") == 0


def test_food_security_share():
    p = plan([cluster()], [TEFF, MAIZE], [DemandSignal("teff", 0, 1e9, price_birr_t=1)],
             PlanningPolicy(food_security={"teff": 0.3}))
    assert p.hectares("X", "teff") >= 30 - 1e-6


def test_infeasible_contract_raises():
    try:
        plan([cluster()], [TEFF], [DemandSignal("teff", 10_000, 20_000)])
    except InfeasiblePlan:
        return
    raise AssertionError("expected InfeasiblePlan")


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"[PASS] {name}")
            except Exception as e:
                failures += 1
                print(f"[FAIL] {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failures else 0)

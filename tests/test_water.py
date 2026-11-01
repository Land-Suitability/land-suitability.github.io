"""Tests for Stage 02. Run: python3 -m pytest tests  (or python3 tests/test_water.py)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from water_res import (ClusterWaterContext, Confidence, CropCoefficients, IrrigatedCropPlan, Method,  # noqa: E402
                       MonthlySeries, SourceType, WaterSource, build_budget, check_allocation,
                       effective_rainfall, et0_hargreaves, extraterrestrial_radiation, irrigation_demand, kc_daily)

CROP = CropCoefficients("test", 0.4, 1.15, 0.3, 20, 30, 50, 30)
FLAT = lambda v: MonthlySeries(tuple([float(v)] * 12), "x")  # noqa: E731


def test_ra_matches_fao56_example_8():
    # FAO-56 Example 8: latitude 20 S, 3 September (day 246) -> Ra = 32.2 MJ m-2 day-1
    assert abs(float(extraterrestrial_radiation(-20.0, 246)) - 32.2) < 0.1


def test_et0_reasonable_for_highlands():
    et0 = et0_hargreaves(11.8, FLAT(10), FLAT(28))
    assert np.all((et0 > 3) & (et0 < 7)), et0


def test_et0_rejects_swapped_temperatures():
    try:
        et0_hargreaves(11.8, FLAT(28), FLAT(10))
    except ValueError:
        return
    raise AssertionError("Tmax < Tmin should raise")


def test_kc_curve_shape():
    kc = kc_daily(IrrigatedCropPlan(CROP, 1))
    assert len(kc) == CROP.season_days == 130
    assert kc[0] == 0.4 and abs(kc[60] - 1.15) < 1e-9 and abs(kc[-1] - 0.3) < 1e-9


def test_effective_rainfall_usda():
    assert abs(float(effective_rainfall(100)) - 84.0) < 1e-9
    assert abs(float(effective_rainfall(300)) - 155.0) < 1e-9


def test_no_demand_when_rain_is_ample_and_season_wraps_year():
    plan = IrrigatedCropPlan(CROP, planting_month=11, planting_day=15)
    wet = irrigation_demand(plan, np.full(12, 4.0), FLAT(400))
    assert np.allclose(wet["net_mm"], 0)
    dry = irrigation_demand(plan, np.full(12, 4.0), FLAT(0))
    assert dry["days"].sum() == 130 and dry["days"][11] == 31 and dry["days"][0] == 31   # Dec and Jan used
    assert np.isclose(dry["gross_m3"].sum(), dry["net_mm"].sum() / Method.FURROW.efficiency * 10)


def test_groundwater_needs_recharge_estimate():
    src = WaterSource("W", SourceType.SHALLOW_WELLS, "w", Confidence.INDICATIVE)
    try:
        src.sustainable_monthly_m3()
    except ValueError:
        return
    raise AssertionError("groundwater without recharge must raise")


def test_environmental_flow_and_capacity():
    src = WaterSource("R", SourceType.RIVER_DIVERSION, "r", Confidence.MEASURED, gross_monthly_m3=FLAT(1000),
                      environmental_flow_fraction=0.3, pump_capacity_m3_per_month=500)
    assert src.sustainable_monthly_m3() == tuple([500.0] * 12)
    src2 = WaterSource("R", SourceType.RIVER_DIVERSION, "r", Confidence.MEASURED, gross_monthly_m3=FLAT(600),
                       environmental_flow_fraction=0.3)
    assert np.allclose(src2.sustainable_monthly_m3(), 420.0)


def test_budget_binding_month_and_monthly_check():
    flow = MonthlySeries((100e3, 20e3) + (100e3,) * 10, "m3")       # February is the lean month
    ctx = ClusterWaterContext("C", 11.8, 1800, 500, [WaterSource("R", SourceType.RIVER_DIVERSION, "r",
                              Confidence.INDICATIVE, gross_monthly_m3=flow)])
    plan = IrrigatedCropPlan(CROP, planting_month=1)
    b = build_budget(ctx, [plan], FLAT(10), FLAT(28), FLAT(0))
    assert b.binding_month["test"] == 1
    ha = b.max_area_ha["test"]
    assert check_allocation(b, {"test": ha * 0.99})["feasible"]
    assert not check_allocation(b, {"test": ha * 1.05})["feasible"]


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

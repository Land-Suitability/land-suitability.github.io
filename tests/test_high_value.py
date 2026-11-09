"""Tests for high-value crop guidance. Run: python3 -m pytest tests  (or python3 tests/test_high_value.py)"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from crop_plan import plan  # noqa: E402
from crop_plan.high_value import (CROPS, HighValueCrop, command_area_units, crop_guide, crop_options,  # noqa: E402
                                  load_module3, market_demand, water_need_m3_ha)

CLIMATE = {"et0_mm_day": [4.0] * 12, "rain_mm": [0.0] * 12}
ONION = next(c for c in CROPS if c.key == "onion")


def test_altitude_bands():
    assert ONION.altitude_factor(1800) == 1.0 and ONION.altitude_factor(2400) == 0.7 and ONION.altitude_factor(3000) == 0.0
    try:
        HighValueCrop("x", "X", (1, 1, 1), (1, 1, 1, 1), (100, 3000), (500, 2000), 1, 1, 1, 0, 1)
    except ValueError:
        return
    raise AssertionError("an optimum outside the acceptable range should raise")


def test_water_need_follows_the_season_and_the_method():
    surf = water_need_m3_ha(ONION, (11, 15), CLIMATE["et0_mm_day"], CLIMATE["rain_mm"], "surface")
    drip = water_need_m3_ha(ONION, (11, 15), CLIMATE["et0_mm_day"], CLIMATE["rain_mm"], "drip")
    assert surf[7] == 0 and surf[0] > 0                      # nothing in August, needs water in January
    assert abs(surf.sum() / drip.sum() - 0.90 / 0.60) < 1e-9
    total_mm = drip.sum() / 10 * 0.90                         # back to crop water use in mm
    assert 4.0 * 0.70 * ONION.field_days < total_mm < 4.0 * 1.05 * ONION.field_days


def test_options_cover_every_crop_date_and_method():
    opts, meta = crop_options(CLIMATE)
    assert len(opts) == len(CROPS) * 4 * 3 and len(meta) == len(opts)


def _handoff(kind="stream", water=None):
    return {"command_areas": [{"source_id": "CA-1", "kind": kind, "mean_altitude_m": 1800, "best_method": "drip",
                               "suitable_ha": {"surface": 0, "sprinkler": 5, "drip": 50},
                               "sustainable_m3": water or [20000.0] * 12}]}


def test_units_use_the_best_method_and_wells_use_storage():
    opts, meta = crop_options(CLIMATE)
    u = command_area_units(_handoff(), meta)[0]
    assert u.area_ha["dry"] == 50
    assert all(meta[o][2] == "drip" for o in u.suitability)
    w = command_area_units(_handoff("groundwater", [1000.0] * 12), meta)[0]
    assert w.water_m3[6] == 0 and abs(sum(w.water_m3) - 12000) < 1e-6     # July empty, the year's water kept


def test_planner_respects_monthly_water_and_markets():
    opts, meta = crop_options(CLIMATE)
    units = command_area_units(_handoff(), meta)
    p = plan(units, opts, market_demand(), plan_id="TEST")
    used = np.zeros(12)
    for a in p.allocations:
        used += np.array(next(o for o in opts if o.option_id == a.option_id).water_m3_ha) * a.hectares
    assert np.all(used <= np.array(units[0].water_m3) + 1e-3)
    assert sum(a.hectares for a in p.allocations) <= 50 + 1e-6
    for c in CROPS:
        assert p.tonnes_by_product.get(c.key, 0) <= c.market_max_t + 1e-6


def test_guide_is_ordered_and_has_a_nursery_only_when_needed():
    g = crop_guide(ONION, (11, 15), "drip", CLIMATE["et0_mm_day"])
    assert g[0].kind == "nursery" and g[0].start < g[1].start
    potato = next(c for c in CROPS if c.key == "potato")
    assert all(s.kind != "nursery" for s in crop_guide(potato, (11, 15), "drip", CLIMATE["et0_mm_day"]))


def test_module3_contract_is_enforced():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "h.json"
        p.write_text(json.dumps({"contract": "other", "version": "0.1"}))
        try:
            load_module3(p)
        except ValueError:
            return
    raise AssertionError("a wrong contract should be rejected")


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  [PASS] {name}")
            except Exception as e:  # debugging block: report and continue
                failed += 1; print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)

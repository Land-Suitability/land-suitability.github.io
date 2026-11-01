#!/usr/bin/env python3
"""
Stage 02 demo on SYNTHETIC data (no real gauge, well or farmer data).

A made-up lake-shore planning cluster (latitude 11.8 N, 1800 m) with a small river diversion and
shallow wells, planning dry-season irrigated wheat and onion.

  1. Sustainable supply per month (environmental flow and recharge limits applied)
  2. ET0 (Hargreaves) and gross irrigation demand per hectare (FAO-56 Kc, USDA-SCS effective rain)
  3. Binding month and maximum irrigable area per crop
  4. Seasonal-total thinking versus monthly thinking for one proposed crop mix
  5. Best crop mix under MONTHLY water limits (the constraint format stage 04 should use)
Writes assets/demo-water-budget.json for the chart on the stage page.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from water_res import (MONTHS, ClusterWaterContext, Confidence, CropCoefficients, IrrigatedCropPlan,  # noqa: E402
                       Method, MonthlySeries, SourceType, WaterSource, build_budget, check_allocation,
                       et0_hargreaves)

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ synthetic inputs
RAIN = MonthlySeries((3, 2, 15, 25, 80, 190, 400, 380, 220, 90, 15, 4), "mm")          # ~1420 mm, Kiremt peak
TMIN = MonthlySeries((8, 9, 11, 13, 14, 14, 14, 14, 13, 12, 10, 8), "°C")
TMAX = MonthlySeries((27, 29, 30, 30, 29, 26, 23, 23, 25, 26, 26, 26), "°C")

WHEAT = CropCoefficients("irrigated_wheat", kc_ini=0.40, kc_mid=1.15, kc_end=0.30, l_ini=20, l_dev=30, l_mid=50, l_late=30)
ONION = CropCoefficients("onion", kc_ini=0.70, kc_mid=1.05, kc_end=0.75, l_ini=15, l_dev=25, l_mid=70, l_late=40)
PLANS = [IrrigatedCropPlan(WHEAT, planting_month=11, planting_day=15, method=Method.FURROW),
         IrrigatedCropPlan(ONION, planting_month=1, planting_day=1, method=Method.FURROW)]

RIVER_FLOW = MonthlySeries((420e3, 320e3, 260e3, 230e3, 300e3, 900e3, 3.0e6, 4.0e6, 2.5e6, 1.2e6, 700e3, 520e3), "m3")


def make_cluster() -> ClusterWaterContext:
    return ClusterWaterContext(
        cluster_id="CLUSTER-DEMO-A", latitude_deg=11.8, altitude_m=1800, irrigable_area_ha=150,
        sources=[
            WaterSource("SRC-RIVER-1", SourceType.RIVER_DIVERSION, "Stream diversion (synthetic)", Confidence.INDICATIVE,
                        gross_monthly_m3=RIVER_FLOW, environmental_flow_fraction=0.30, pump_capacity_m3_per_month=450e3),
            WaterSource("SRC-WELLS-1", SourceType.SHALLOW_WELLS, "Shallow wells on the plain (synthetic)", Confidence.INDICATIVE,
                        annual_recharge_m3=1.2e6, recharge_share=0.40),
        ])


def main() -> int:
    try:
        ctx = make_cluster()
        budget = build_budget(ctx, PLANS, TMIN, TMAX, RAIN, season="dry")
        et0 = et0_hargreaves(ctx.latitude_deg, TMIN, TMAX)

        print("== 1-2. Monthly supply, ET0 and gross demand per ha ==")
        print(f"{'':5s}{'rain':>7s}{'ET0':>7s}{'supply m3':>12s}" + "".join(f"{p.crop.crop[:12]:>16s}" for p in PLANS))
        for m in range(12):
            row = f"{MONTHS[m]:5s}{RAIN[m]:7.0f}{et0[m]:7.2f}{budget.supply_m3[m]:12,.0f}"
            row += "".join(f"{budget.demand_m3_per_ha[p.crop.crop][m]:16,.0f}" for p in PLANS)
            print(row)
        for p in PLANS:
            total = sum(budget.demand_m3_per_ha[p.crop.crop])
            print(f"  [DEBUG] {p.crop.crop}: seasonal gross demand {total:,.0f} m3/ha ({total / 10:.0f} mm), "
                  f"{p.crop.season_days} days")

        print("\n== 3. Binding month and maximum area (each crop alone) ==")
        for crop, ha in budget.max_area_ha.items():
            print(f"  {crop:16s} max {ha:6.1f} ha, limited by {MONTHS[budget.binding_month[crop]]}")
        print(f"  seasonal sustainable supply: {budget.seasonal_supply_m3:,.0f} m3 | confidence: {budget.confidence.value}")

        print("\n== 4. Seasonal total versus monthly check for 70 ha wheat + 40 ha onion ==")
        mix = {"irrigated_wheat": 70.0, "onion": 40.0}
        chk = check_allocation(budget, mix)
        dry = [10, 11, 0, 1, 2, 3, 4]          # Nov..May
        seasonal_supply = sum(budget.supply_m3[m] for m in dry)
        seasonal_use = sum(chk["use_m3"][m] for m in dry)
        print(f"  Nov-May totals: use {seasonal_use:,.0f} m3 vs supply {seasonal_supply:,.0f} m3 "
              f"-> {'looks fine' if seasonal_use <= seasonal_supply else 'deficit'} on a seasonal basis")
        print(f"  Monthly check: feasible={chk['feasible']}, deficit months: {[MONTHS[m] for m in chk['deficit_months']]}")

        print("\n== 5. Best mix under monthly limits (input for stage 04) ==")
        try:
            from scipy.optimize import linprog
            margin = {"irrigated_wheat": 60_000, "onion": 110_000}     # illustrative birr/ha net margin
            crops = list(margin)
            A = np.array([[budget.demand_m3_per_ha[c][m] for c in crops] for m in range(12)])
            A = np.vstack([A, np.ones(len(crops))])
            b = np.concatenate([budget.supply_m3, [ctx.irrigable_area_ha]])
            res = linprog([-margin[c] for c in crops], A_ub=A, b_ub=b, bounds=[(0, None)] * len(crops), method="highs")
            if not res.success:
                raise RuntimeError(res.message)
            best = dict(zip(crops, res.x))
            print("  " + ", ".join(f"{c} {ha:.1f} ha" for c, ha in best.items()) + f" | net margin {-res.fun:,.0f} birr")
            tight = [MONTHS[m] for m in range(12) if abs(res.ineqlin.residual[m]) < 1.0]
            print(f"  [DEBUG] binding months for this mix: {tight}")
        except ImportError:
            best = mix
            print("  scipy not installed, skipping optimisation")

        chk_best = check_allocation(budget, best)
        out = {
            "cluster": ctx.cluster_id, "synthetic": True, "months": list(MONTHS),
            "supply_m3": [round(x) for x in budget.supply_m3],
            "mix_ha": {c: round(h, 1) for c, h in best.items()},
            "demand_m3": {c: [round(best[c] * x) for x in budget.demand_m3_per_ha[c]] for c in best},
            "balance_m3": [round(x) for x in chk_best["balance_m3"]],
            "et0_mm_day": [round(float(x), 2) for x in et0], "rain_mm": list(RAIN.values),
            "max_area_ha": {c: round(v, 1) for c, v in budget.max_area_ha.items()},
            "binding_month": {c: MONTHS[m] for c, m in budget.binding_month.items()},
        }
        path = ROOT / "assets" / "demo-water-budget.json"
        path.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"  [DEBUG] wrote {path.relative_to(ROOT)}")
        return 0
    except (KeyError, ValueError) as e:
        print(f"[DATA ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Stage 04 demo on SYNTHETIC inputs (illustrative prices, yields and costs; no real farm data).

Three planning clusters, two seasons:
  Meher (rainfed): teff, maize, bread wheat      Dry season (irrigated): wheat, onion
Inputs mimic the contracts of the other stages:
  suitability (01), monthly water supply and demand curves (02), crop-cycle fit (03), buyer demand (05)

  1. Solve the market-backwards plan
  2. Show which limits bind (shadow prices) as investment and negotiation signals
  3. Show what happens if a buyer demands more wheat than the land and water can give
Writes assets/demo-plan.json for the chart.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crop_plan import (MONTHS, ClusterProfile, CropOption, DemandSignal, InfeasiblePlan, PlanningPolicy,  # noqa: E402
                       expected_yield, plan)

ROOT = Path(__file__).resolve().parent.parent

# gross irrigation demand per ha per month, from the stage 02 demo (furrow irrigation)
W_WHEAT = (2607, 2714, 1245, 0, 0, 0, 0, 0, 0, 0, 323, 1450)
W_ONION = (1713, 2478, 2864, 2594, 1201, 0, 0, 0, 0, 0, 0, 0)
SUPPLY_A = (334e3, 264e3, 222e3, 201e3, 250e3, 490e3, 490e3, 490e3, 490e3, 490e3, 490e3, 404e3)

OPTIONS = [
    CropOption("teff_meher", "teff", "meher", 110, 2.0, 95_000, 40_000),
    CropOption("maize_meher", "maize", "meher", 150, 5.0, 30_000, 45_000),
    CropOption("wheat_meher", "wheat", "meher", 130, 3.5, 45_000, 55_000),
    CropOption("wheat_dry", "wheat", "dry", 130, 4.5, 45_000, 70_000, water_m3_ha=W_WHEAT),
    CropOption("onion_dry", "onion", "dry", 150, 20.0, 18_000, 150_000, water_m3_ha=W_ONION),
]

CLUSTERS = [
    ClusterProfile("A", {"meher": 300, "dry": 150},
                   {"teff_meher": 0.95, "maize_meher": 0.80, "wheat_meher": 0.70, "wheat_dry": 0.90, "onion_dry": 0.95},
                   {"maize_meher": 0.67, "wheat_meher": 0.90}, SUPPLY_A),
    ClusterProfile("B", {"meher": 250, "dry": 120},
                   {"teff_meher": 0.80, "maize_meher": 0.60, "wheat_meher": 0.95, "wheat_dry": 0.95, "onion_dry": 0.70},
                   {"maize_meher": 0.40, "wheat_meher": 0.95}, tuple(v * 1.4 for v in SUPPLY_A)),
    ClusterProfile("C", {"meher": 400, "dry": 0},
                   {"teff_meher": 0.90, "maize_meher": 0.95, "wheat_meher": 0.55, "wheat_dry": 0.0, "onion_dry": 0.0},
                   {"maize_meher": 0.85, "wheat_meher": 0.80}),
]

DEMAND = [
    DemandSignal("teff", min_t=150, max_t=900),
    DemandSignal("wheat", min_t=900, max_t=1400, price_birr_t=46_000),    # flour-mill contract
    DemandSignal("maize", min_t=0, max_t=1500),
    DemandSignal("onion", min_t=0, max_t=2000),
]
POLICY = PlanningPolicy(food_security={"teff": 0.20}, max_share={"maize": 0.40, "teff": 0.60})


def main() -> int:
    try:
        for c in CLUSTERS:
            ys = ", ".join(f"{o.option_id} {expected_yield(o, c):.2f}" for o in OPTIONS if c.suitability.get(o.option_id, 0) > 0)
            print(f"[DEBUG] expected t/ha in {c.cluster_id}: {ys}")

        p = plan(CLUSTERS, OPTIONS, DEMAND, POLICY)
        print("\n== 1. Plan ==")
        for a in p.allocations:
            print(f"  cluster {a.cluster_id}  {a.option_id:12s} {a.hectares:7.1f} ha  {a.expected_t:7.0f} t  net {a.expected_net_birr:12,.0f} birr")
        print("  tonnes: " + ", ".join(f"{k} {v:,.0f}" for k, v in p.tonnes_by_product.items()))
        print(f"  total expected net income: {p.total_net_birr:,.0f} birr")

        print("\n== 2. What binds (shadow prices) ==")
        for s in p.binding[:10]:
            unit = "m3" if s.constraint.startswith("water") else ("ha" if s.constraint.startswith("land") else "t" if "demand" in s.constraint else "unit")
            print(f"  {s.constraint:28s} {s.value_birr:10,.1f} birr per extra {unit}")

        print("\n== 3. Stress test: buyer asks for 3,500 t wheat minimum ==")
        stressed = [d if d.product != "wheat" else DemandSignal("wheat", 3500, 4000, 46_000) for d in DEMAND]
        try:
            plan(CLUSTERS, OPTIONS, stressed, POLICY)
            print("  feasible")
        except InfeasiblePlan as e:
            print(f"  infeasible -> {e}")

        crops = ["teff", "maize", "wheat", "onion"]
        cats = [f"{c.cluster_id} {s}" for c in CLUSTERS for s in ("meher", "dry") if c.area_ha.get(s, 0) > 0]
        series = {k: [] for k in crops}
        for cat in cats:
            cid, season = cat.split()
            for k in crops:
                series[k].append(round(sum(a.hectares for a in p.allocations
                                           if a.cluster_id == cid and a.season == season and a.product == k), 1))
        out = {"categories": cats, "series": series, "total_net_birr": round(p.total_net_birr),
               "tonnes": {k: round(v) for k, v in p.tonnes_by_product.items()},
               "binding": [{"constraint": s.constraint, "value": round(s.value_birr, 2)} for s in p.binding[:10]],
               "allocations": [a.__dict__ for a in p.allocations]}
        path = ROOT / "assets" / "demo-plan.json"
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

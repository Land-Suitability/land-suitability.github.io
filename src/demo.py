#!/usr/bin/env python3
"""
Stage 06 demo on SYNTHETIC data (indicative input rates, made-up suppliers and prices).

Takes the stage 04 demo plan, explodes it into dated input requirements (with lime on the acidic share
of cluster A flagged by stage 01), allocates orders across suppliers and back-schedules order dates for
a 90% on-time target. Writes assets/demo-inputs.json for the charts.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inputs import InputItem, InputNorm, Supplier, allocate, explode_plan, lead_quantile, p_on_time  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# allocations from the stage 04 demo plan (hectares)
PLAN = [
    {"cluster_id": "A", "option_id": "teff_meher", "hectares": 180.0}, {"cluster_id": "A", "option_id": "maize_meher", "hectares": 120.0},
    {"cluster_id": "A", "option_id": "wheat_dry", "hectares": 43.9}, {"cluster_id": "A", "option_id": "onion_dry", "hectares": 58.4},
    {"cluster_id": "B", "option_id": "teff_meher", "hectares": 78.8}, {"cluster_id": "B", "option_id": "wheat_meher", "hectares": 171.2},
    {"cluster_id": "B", "option_id": "wheat_dry", "hectares": 120.0}, {"cluster_id": "C", "option_id": "teff_meher", "hectares": 240.0},
    {"cluster_id": "C", "option_id": "maize_meher", "hectares": 160.0},
]
PLANTING = {"maize_meher": date(2026, 6, 1), "wheat_meher": date(2026, 6, 20), "teff_meher": date(2026, 7, 10),
            "wheat_dry": date(2026, 11, 15), "onion_dry": date(2027, 1, 1)}

I = {k: InputItem(k, n, "kg") for k, n in [("seed_teff", "Teff seed"), ("seed_maize", "Hybrid maize seed"),
                                            ("seed_wheat", "Bread wheat seed"), ("seed_onion", "Onion seed"),
                                            ("nps", "NPS fertilizer"), ("urea", "Urea"), ("lime", "Agricultural lime")]}
NORMS = []
for opt, seed, sr, nps, urea in [("teff_meher", "seed_teff", 15, 100, 100), ("maize_meher", "seed_maize", 25, 150, 200),
                                 ("wheat_meher", "seed_wheat", 150, 150, 150), ("wheat_dry", "seed_wheat", 150, 150, 150),
                                 ("onion_dry", "seed_onion", 4, 200, 200)]:
    NORMS += [InputNorm(opt, I[seed], sr, -10), InputNorm(opt, I["nps"], nps, -7),
              InputNorm(opt, I["urea"], urea * 0.5, 0), InputNorm(opt, I["urea"], urea * 0.5, 35)]
# lime: 3 t/ha on the acidic share (soil pH < 5.5) of cluster A, flagged by stage 01 limiting factors
LIME_SHARE_A = 0.30

SUPPLIERS = [
    Supplier("UNION-1", "cooperative_union", ("nps", "urea", "lime"), {"nps": 120_000, "urea": 110_000, "lime": 200_000},
             {"nps": 75, "urea": 70, "lime": 3}, lead_median_days=30, lead_spread=0.45),
    Supplier("SEED-ENT", "seed_enterprise", ("seed_teff", "seed_maize", "seed_wheat"),
             {"seed_teff": 8_000, "seed_maize": 6_000, "seed_wheat": 30_000}, {"seed_teff": 90, "seed_maize": 160, "seed_wheat": 60},
             lead_median_days=40, lead_spread=0.35),
    Supplier("DEALER-7", "agro_dealer", ("nps", "urea", "seed_onion", "seed_wheat"),
             {"nps": 30_000, "urea": 30_000, "seed_onion": 400, "seed_wheat": 20_000},
             {"nps": 85, "urea": 80, "seed_onion": 4_000, "seed_wheat": 70}, lead_median_days=12, lead_spread=0.25),
]


def main() -> int:
    try:
        reqs = explode_plan(PLAN, NORMS, PLANTING)
        lime_need = [a for a in PLAN if a["cluster_id"] == "A" and a["option_id"].endswith("meher")]
        lime_norms = [InputNorm(a["option_id"], I["lime"], 3000, -45, LIME_SHARE_A) for a in lime_need]
        reqs += explode_plan(lime_need, lime_norms, PLANTING)
        print(f"== 1. {len(reqs)} dated requirements ==")
        tot = defaultdict(float)
        for r in reqs:
            tot[r.item.code] += r.quantity
        for k, v in tot.items():
            print(f"  {k:11s} {v:12,.0f} kg")

        orders, warnings = allocate(reqs, SUPPLIERS, target=0.9, today=date(2026, 3, 1))
        print(f"\n== 2. {len(orders)} purchase orders (target 90% on time) ==")
        for o in sorted(orders, key=lambda o: o.order_by)[:12]:
            print(f"  order by {o.order_by}  {o.supplier_id:9s} {o.item_code:10s} {o.quantity:10,.0f} kg for {o.cluster_id}"
                  f"  need {o.need_by}  P(on time) {o.p_on_time:.0%}")
        print(f"  ... total input cost {sum(o.cost_birr for o in orders):,.0f} birr")
        print("\n== 3. Warnings ==")
        for w in warnings or ["none"]:
            print("  " + w)

        days = list(range(5, 91, 5))
        curves = {s.supplier_id: [round(p_on_time(s, d) * 100, 1) for d in days] for s in SUPPLIERS}
        for s in SUPPLIERS:
            print(f"  [DEBUG] {s.supplier_id}: order {lead_quantile(s, 0.9):.0f} days ahead for 90% on time (median lead {s.lead_median_days} d)")
        meher = [o for o in orders if o.need_by.year == 2026 and o.need_by.month <= 8]
        by_month = defaultdict(float)
        for o in meher:
            by_month[o.order_by.strftime("%Y-%m")] += o.quantity / 1000
        out = {"days": days, "curves": curves,
               "order_months": sorted(by_month), "order_t": [round(by_month[m], 1) for m in sorted(by_month)],
               "totals_kg": {k: round(v) for k, v in tot.items()}, "warnings": warnings,
               "orders": [{**o.__dict__, "need_by": str(o.need_by), "order_by": str(o.order_by),
                           "quantity": round(o.quantity), "p_on_time": round(o.p_on_time, 3), "cost_birr": round(o.cost_birr)}
                          for o in sorted(orders, key=lambda o: o.order_by)],
               "cost_total": round(sum(o.cost_birr for o in orders))}
        path = ROOT / "assets" / "demo-inputs.json"
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

#!/usr/bin/env python3
"""
Stage 10 demo on SYNTHETIC geography and volumes (no real sites or farmer data).

  1. Choose 1 to 4 collection centres among 8 candidate sites for 30 kebeles (p-median with capacity)
  2. Store or sell: value per tonne of teff sold 0 to 8 months after the November harvest, for traditional
     bags versus hermetic bags, using the seasonal price index from stage 05
  3. Weekly inventory at the main centre versus its capacity
Writes assets/demo-storage.json for the charts.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from storage import CandidateSite, StorageTech, SupplyPoint, WarehouseReceipt, locate_centres, simulate_inventory, store_or_sell  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# seasonal price index from the stage 05 demo (January first): low after harvest, high in the lean season
PRICE_INDEX = [0.93, 0.97, 0.99, 0.99, 1.07, 1.06, 1.06, 1.07, 1.04, 1.00, 0.94, 0.89]
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def main() -> int:
    try:
        rng = np.random.default_rng(21)
        points = [SupplyPoint(f"K{i:02d}", float(x), float(y), float(t)) for i, (x, y, t) in
                  enumerate(zip(rng.uniform(0, 40, 30), rng.uniform(0, 30, 30), rng.gamma(4, 15, 30)))]
        total = sum(p.tonnes for p in points)
        cands = [CandidateSite(f"S{i}", float(x), float(y), cap, cost, existing=i < 3) for i, (x, y, cap, cost) in
                 enumerate([(8, 8, 900, 0), (30, 22, 900, 0), (20, 15, 700, 0), (35, 5, 1500, 4e6), (5, 25, 1500, 4e6),
                            (20, 28, 1500, 4e6), (12, 15, 2500, 6e6), (28, 12, 2500, 6e6)])]
        print(f"== 1. {len(points)} kebeles, {total:,.0f} t to aggregate")
        loc = []
        for p in range(1, 5):
            try:
                centres, tkm = locate_centres(points, cands, p)
                loc.append({"p": p, "sites": [c.site.site_id for c in centres], "avg_km": round(tkm / total, 1),
                            "tonnes": [round(c.tonnes) for c in centres]})
                print(f"  p={p}: sites {loc[-1]['sites']}  average haul {tkm / total:5.1f} km per tonne  load {loc[-1]['tonnes']}")
            except RuntimeError as e:
                loc.append({"p": p, "sites": [], "avg_km": None, "tonnes": []})
                print(f"  p={p}: {e}")

        print("\n== 2. Store or sell (teff, harvest in November, base 95,000 birr/t)")
        techs = [StorageTech("Traditional bags", 0.025, 150), StorageTech("Hermetic bags", 0.004, 250)]
        curves = {t.name: store_or_sell(PRICE_INDEX, 11, t, 95_000) for t in techs}
        for name, v in curves.items():
            best = int(np.argmax(v))
            print(f"  {name:17s} best: sell after {best} months ({MONTHS[(10 + best) % 12]}), "
                  f"{v[best]:,.0f} vs {v[0]:,.0f} birr/t at harvest ({v[best] / v[0] - 1:+.1%})")

        receipt = WarehouseReceipt("WR-0001", "LOT-A-TEFF-2026-W43-001", "COOP-A-01", "teff", "grade 1", 9_468, __import__("datetime").date(2026, 10, 28), "S6")
        print(f"  [DEBUG] example receipt: {receipt}")

        weeks = 30
        inflow = [0.0] * weeks
        for w in range(2, 9):
            inflow[w] = 260.0                                   # harvest lots arriving (stage 09)
        outflow = [0.0] * weeks
        for w in range(4, weeks):
            outflow[w] = 60.0 if w < 12 else 90.0               # contract deliveries, then lean-season sales
        stock, over = simulate_inventory(inflow, outflow, capacity_t=1200)
        print(f"\n== 3. Inventory: peak {stock.max():,.0f} t in week {int(stock.argmax())}; weeks over 1,200 t capacity: {over}")

        out = {"locations": loc, "points": [p.__dict__ for p in points], "candidates": [c.__dict__ for c in cands],
               "store_months": [MONTHS[(10 + m) % 12] for m in range(9)],
               "store": {k: [round(x) for x in v] for k, v in curves.items()},
               "weeks": [f"W{w + 1}" for w in range(weeks)], "stock": [round(float(s)) for s in stock], "capacity": 1200,
               "over_weeks": over, "receipt": {**receipt.__dict__, "deposited": str(receipt.deposited)}}
        path = ROOT / "assets" / "demo-storage.json"
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

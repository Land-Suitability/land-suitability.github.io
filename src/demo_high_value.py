#!/usr/bin/env python3
"""
High-value crop guidance demo (Phase 1, module 4) on the command areas from module 3. Synthetic data.

  1. Read module 3's hand-off (data/handoff-module3.json): command areas, their water and the climate.
  2. Offer onion, tomato, hot pepper, potato and garlic at four planting dates under each method.
  3. Let the stage 04 planner choose crops, dates and hectares within land, monthly water and markets.
  4. Compare with one crop (onion) and with a single planting date, to show what mixing and staggering add.
  5. Write assets/demo-high-value.json (plan, comparisons, water use, guides) for the page.

Run from the branch root:  python3 src/demo_high_value.py
"""
from __future__ import annotations

import json
import sys
import traceback
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crop_plan import plan  # noqa: E402
from crop_plan.high_value import (CROPS, MONTHS, command_area_units, crop_guide, crop_options, load_module3,  # noqa: E402
                                  market_demand)

ROOT = Path(__file__).resolve().parent.parent


def summarise(p, meta):
    by_crop, by_date = defaultdict(float), defaultdict(float)
    for a in p.allocations:
        if a.hectares < 0.05:
            continue
        crop, plant, _m = meta[a.option_id]
        by_crop[crop.key] += a.hectares
        by_date[(crop.key, MONTHS[plant[0] - 1])] += a.hectares
    return by_crop, by_date


def main() -> int:
    try:
        h = load_module3(ROOT / "data" / "handoff-module3.json")
        opts, meta = crop_options(h["climate"])
        units = command_area_units(h, meta)
        land = sum(u.area_ha["dry"] for u in units)
        print(f"== Inputs from module 3 ({h['provenance']['branch']} @ {h['provenance']['commit']}): {len(units)} command areas, "
              f"{land:,.0f} ha suitable for their best method; {len(opts)} crop options (5 crops x 4 dates x 3 methods) ==")

        best = plan(units, opts, market_demand(), plan_id="HV-BEST")
        by_crop, by_date = summarise(best, meta)
        total_ha = sum(by_crop.values())
        print(f"\n== Recommended plan: {total_ha:,.0f} ha, net income {best.total_net_birr / 1e6:,.1f} million birr ==")
        for c in CROPS:
            if by_crop.get(c.key):
                dates = ", ".join(f"{m} {ha:,.0f} ha" for (k, m), ha in by_date.items() if k == c.key)
                print(f"  {c.name:11s} {by_crop[c.key]:6,.1f} ha  {best.tonnes_by_product.get(c.key, 0):6,.0f} t  (planted {dates})")

        # what mixing and staggering are worth
        onion_only = plan(units, [o for o in opts if meta[o.option_id][0].key == "onion"], market_demand(), plan_id="ONION")
        one_date = plan(units, [o for o in opts if meta[o.option_id][1] == (11, 15)], market_demand(), plan_id="NOV")
        print(f"\n== Comparisons (net income) ==\n  recommended mix  {best.total_net_birr / 1e6:6.1f} M birr"
              f"\n  onion only       {onion_only.total_net_birr / 1e6:6.1f} M birr ({sum(a.hectares for a in onion_only.allocations):,.0f} ha)"
              f"\n  all planted mid-November {one_date.total_net_birr / 1e6:6.1f} M birr ({sum(a.hectares for a in one_date.allocations):,.0f} ha)")

        markets = sorted([b for b in best.binding if b.constraint.startswith("demand")], key=lambda b: -b.value_birr)
        water = sorted([b for b in best.binding if b.constraint.startswith("water")], key=lambda b: -b.value_birr)[:4]
        binding = markets + water
        print("\n== What binds (shadow prices) ==")
        for b in markets:
            print(f"  {b.constraint:28s} {b.value_birr:10,.0f} birr per extra tonne of market")
        for b in water:
            print(f"  {b.constraint:28s} {b.value_birr:10,.1f} birr per extra m3")

        # water use in the largest command area, month by month, by crop
        big = max(units, key=lambda u: u.area_ha["dry"])
        use = defaultdict(lambda: np.zeros(12))
        for a in best.allocations:
            if a.cluster_id == big.cluster_id and a.hectares > 0.05:
                o = next(x for x in opts if x.option_id == a.option_id)
                use[meta[a.option_id][0].key] += np.array(o.water_m3_ha) * a.hectares
        print(f"  [DEBUG] {big.cluster_id}: water used in its tightest month "
              f"{max(sum(v[m] for v in use.values()) / big.water_m3[m] for m in range(12) if big.water_m3[m] > 0):.0%}")

        # guides for every recommended crop at its main planting date
        guides = {}
        for c in CROPS:
            dates = {m: ha for (k, m), ha in by_date.items() if k == c.key}
            if not dates:
                continue
            main_m = max(dates, key=dates.get)
            plant = next(pd for pd in [(10, 15), (11, 15), (12, 15), (1, 15)] if MONTHS[pd[0] - 1] == main_m)
            steps = crop_guide(c, plant, "drip", h["climate"]["et0_mm_day"])
            guides[c.key] = {"name": c.name, "planting": f"15 {main_m}", "field_days": c.field_days, "margin_birr_ha": c.margin_birr_ha,
                             "steps": [{"start": s.start.isoformat(), "end": s.end.isoformat(), "what": s.what, "kind": s.kind} for s in steps]}

        per_area = []
        for u in sorted(units, key=lambda u: -u.area_ha["dry"]):
            rows = [(meta[a.option_id][0].name, MONTHS[meta[a.option_id][1][0] - 1], a.hectares) for a in best.allocations
                    if a.cluster_id == u.cluster_id and a.hectares > 0.05]
            if rows:
                per_area.append({"area": u.cluster_id, "suitable_ha": u.area_ha["dry"], "planted_ha": round(sum(r[2] for r in rows), 1),
                                 "crops": [{"crop": r[0], "planted": r[1], "ha": round(r[2], 1)} for r in sorted(rows, key=lambda r: -r[2])]})

        out = {"note": "Synthetic command areas from module 3; indicative crop economics v0.1. Not real prices or advice.",
               "provenance": h["provenance"], "command_areas": len(units), "suitable_ha": land, "planted_ha": total_ha,
               "net_income_birr": best.total_net_birr, "ha_by_crop": dict(by_crop), "tonnes_by_crop": best.tonnes_by_product,
               "ha_by_crop_and_month": [{"crop": k, "month": m, "ha": v} for (k, m), v in by_date.items()],
               "comparisons": {"recommended": best.total_net_birr, "onion_only": onion_only.total_net_birr, "single_date_nov": one_date.total_net_birr},
               "binding": [{"constraint": s.constraint, "value_birr": s.value_birr} for s in binding],
               "largest_area": {"id": big.cluster_id, "supply_m3": list(big.water_m3), "use_m3": {k: list(v) for k, v in use.items()}},
               "crops": [{"key": c.key, "name": c.name, "yield_t_ha": c.yield_t_ha, "price_birr_t": c.price_birr_t, "cost_birr_ha": c.cost_birr_ha,
                          "margin_birr_ha": c.margin_birr_ha, "field_days": c.field_days, "altitude_opt": c.altitude_opt,
                          "market_max_t": c.market_max_t, "kc": c.kc, "stages": c.stages, "nursery_days": c.nursery_days} for c in CROPS],
               "climate": h["climate"], "per_area": per_area, "guides": guides}
        (ROOT / "assets" / "demo-high-value.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print("  [DEBUG] wrote assets/demo-high-value.json")
        return 0
    except (KeyError, ValueError, FileNotFoundError) as e:
        print(f"[DATA ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

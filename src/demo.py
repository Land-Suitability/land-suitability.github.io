#!/usr/bin/env python3
"""
Stage 09 demo on SYNTHETIC plots (maturity windows, yields and moisture are generated).

Teff harvest in cluster A: 180 plots, two threshers and one hand-harvest crew.
  1. Schedule harvests first-come-first-served (FIFO) versus earliest deadline first (EDF)
  2. Losses by step: field (late harvest), threshing, drying (water removed), handling
  3. Dry to 12.5%, grade and form traceable lots
Writes assets/demo-harvest.json for the charts.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest import (GradeSpec, HarvestResource, MaturityWindow, dry_weight, field_loss_share, form_lots,  # noqa: E402
                     grade_of, schedule)

ROOT = Path(__file__).resolve().parent.parent
START = date(2026, 10, 20)
GRADES = [GradeSpec("grade 1", 12.5, 1.0), GradeSpec("grade 2", 13.5, 2.0), GradeSpec("grade 3", 14.5, 3.0)]


def synthetic_windows(seed: int = 4) -> list[MaturityWindow]:
    rng = np.random.default_rng(seed)
    out = []
    for i in range(180):
        ready = START + timedelta(days=int(rng.integers(0, 21)))
        area = float(np.round(rng.uniform(0.2, 0.9), 2))
        out.append(MaturityWindow(f"P-{i:03d}", "A", "teff", area, area * float(rng.normal(1.9, 0.25)),
                                  ready, ready + timedelta(days=int(rng.integers(6, 11)))))
    rng.shuffle(out)                     # requests arrive in random order (FIFO uses this order)
    return out


def tonnes_by_grade(lots) -> dict:
    t = defaultdict(float)
    for l in lots:
        t[l.grade] += l.weight_kg / 1000
    return {g: round(v, 1) for g, v in sorted(t.items())}


def run(windows, resources, policy, rng, tarp_share: float = 0.5):
    jobs = {j.plot_id: j for j in schedule(windows, resources, policy)}
    losses = Counter()
    harvested = []
    for w in windows:
        j = jobs[w.plot_id]
        kg0 = w.expected_t * 1000
        field = kg0 * field_loss_share(j.days_late)
        thresh = (kg0 - field) * 0.02
        kg = kg0 - field - thresh
        m0 = float(rng.uniform(12, 18)) + 0.2 * j.days_late * (rng.random() < 0.3)     # late plots may catch rain
        m1 = 12.5 if m0 > 12.5 else m0
        dried = dry_weight(kg, m0, m1)
        handling = dried * 0.01
        losses.update({"Field (late harvest)": field, "Threshing": thresh, "Drying (water removed)": kg - dried,
                       "Handling": handling})
        tarp = rng.random() < tarp_share                            # share of plots threshed on tarpaulins
        harvested.append({"plot_id": w.plot_id, "cluster_id": w.cluster_id, "product": w.product, "day": j.day,
                          "kg": dried - handling, "moisture": m1, "floor": "tarpaulin" if tarp else "bare ground",
                          "foreign": float(rng.uniform(0.3, 0.9) if tarp else rng.uniform(1.2, 2.8))})
    late = sum(j.days_late > 0 for j in jobs.values())
    return jobs, losses, harvested, late


def main() -> int:
    try:
        windows = synthetic_windows()
        days = tuple(START + timedelta(days=k) for k in range(40) if (START + timedelta(days=k)).weekday() != 6)  # no Sundays
        resources = [HarvestResource("THRESHER-1", "thresher", 2.0, days), HarvestResource("THRESHER-2", "thresher", 2.0, days),
                     HarvestResource("CREW-1", "crew", 1.0, days)]
        print(f"[DEBUG] {len(windows)} plots, {sum(w.area_ha for w in windows):.1f} ha, capacity {sum(r.ha_per_day for r in resources)} ha/day")
        out = {"steps": [], "fifo": [], "edf": []}
        res = {}
        for policy in ("fifo", "edf"):
            rng = np.random.default_rng(1)
            jobs, losses, harvested, late = run(windows, resources, policy, rng)
            total_in = sum(w.expected_t for w in windows) * 1000
            field_share = losses["Field (late harvest)"] / total_in
            res[policy] = (jobs, losses, harvested, late)
            print(f"== {policy.upper()}: {late} plots harvested late; field loss {field_share:.1%}; "
                  f"delivered {sum(h['kg'] for h in harvested) / 1000:.1f} t of {total_in / 1000:.1f} t harvested potential")
        steps = list(res["edf"][1].keys())
        out["steps"] = steps
        out["fifo"] = [round(res["fifo"][1][s] / 1000, 2) for s in steps]
        out["edf"] = [round(res["edf"][1][s] / 1000, 2) for s in steps]

        mixed = form_lots(res["edf"][2])
        for lot in mixed:
            lot.grade = grade_of(lot.moisture, lot.foreign, GRADES)
        print(f"\n== Without segregation, tonnes by grade: {tonnes_by_grade(mixed)}")
        lots = form_lots(res["edf"][2], segregate_by="floor")
        all_tarp = form_lots(run(windows, resources, "edf", np.random.default_rng(1), tarp_share=1.0)[2])
        for lot in all_tarp:
            lot.grade = grade_of(lot.moisture, lot.foreign, GRADES)
        for lot in lots:
            lot.grade = grade_of(lot.moisture, lot.foreign, GRADES)
        print(f"== Segregated by threshing floor: {len(lots)} lots, tonnes by grade: {tonnes_by_grade(lots)}")
        premium = {"grade 1": 1.08, "grade 2": 1.0, "grade 3": 0.92, "below grade": 0.8}
        value = lambda ls: sum(l.weight_kg / 1000 * premium[l.grade] for l in ls)  # noqa: E731
        print(f"== All plots on tarpaulins: tonnes by grade {tonnes_by_grade(all_tarp)}")
        print(f"  [DEBUG] value index (grade-2 tonnes equivalent, +/-8% premiums): mixed {value(mixed):.1f}, "
              f"segregated {value(lots):.1f}, all tarpaulins {value(all_tarp):.1f}")
        for lot in lots[:3]:
            print(f"  {lot.lot_id}: {lot.weight_kg:7,.0f} kg, {len(lot.plot_ids)} plots, moisture {lot.moisture:.1f}%, "
                  f"foreign {lot.foreign:.1f}%, {lot.grade}")

        daily = defaultdict(float)
        area = {w.plot_id: w.area_ha for w in windows}
        for j in res["edf"][0].values():
            daily[j.day] += area[j.plot_id]
        dd = sorted(daily)
        out.update({
            "days": [d.strftime("%d %b") for d in dd], "ha_done": [round(daily[d], 1) for d in dd],
            "capacity": sum(r.ha_per_day for r in resources), "late": {"fifo": res["fifo"][3], "edf": res["edf"][3]},
            "delivered_t": {p: round(sum(h["kg"] for h in res[p][2]) / 1000, 1) for p in res},
            "grades_mixed_t": tonnes_by_grade(mixed), "grades_segregated_t": tonnes_by_grade(lots), "grades_all_tarp_t": tonnes_by_grade(all_tarp),
            "value_index": {"mixed": round(value(mixed), 1), "segregated": round(value(lots), 1), "all_tarp": round(value(all_tarp), 1)},
            "lots": [{"lot_id": l.lot_id, "weight_kg": round(l.weight_kg), "plots": len(l.plot_ids), "plot_ids": l.plot_ids[:4],
                      "moisture": round(l.moisture, 1), "foreign": round(l.foreign, 2), "grade": l.grade, "week": l.harvest_week} for l in lots],
        })
        path = ROOT / "assets" / "demo-harvest.json"
        path.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"  [DEBUG] wrote {path.relative_to(ROOT)}")
        return 0
    except (KeyError, ValueError, RuntimeError) as e:
        print(f"[DATA ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

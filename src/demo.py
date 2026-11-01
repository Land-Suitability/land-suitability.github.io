#!/usr/bin/env python3
"""
Stage 07 demo on SYNTHETIC households (pseudonymous IDs, generated plots and reports; no real farmers).

Cluster A from the stage 04 plan: 180 ha teff and 120 ha maize in Meher.
  1. Assign plots to crops (suitability first, only willing households)
  2. Build the operations calendar
  3. Simulate development-agent reports up to 31 August and score adherence by kebele
  4. Pick this week's extension visits
Writes assets/demo-farm.json for the charts.

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
from farm_ops import (FieldReport, Household, HouseholdPlot, OperationTemplate, adherence, assign_plots,  # noqa: E402
                      build_calendar, prioritise_visits)

ROOT = Path(__file__).resolve().parent.parent
KEBELES = ["Kebele 1", "Kebele 2", "Kebele 3", "Kebele 4"]
PLANTING = {"teff_meher": date(2026, 7, 10), "maize_meher": date(2026, 6, 1)}
TEMPLATES = [
    OperationTemplate("maize_meher", "land_prep", -20, 10), OperationTemplate("maize_meher", "planting", 0, 7),
    OperationTemplate("maize_meher", "basal_fert", 0, 5), OperationTemplate("maize_meher", "weeding", 25, 7),
    OperationTemplate("maize_meher", "top_dress", 35, 7), OperationTemplate("maize_meher", "weeding", 50, 10),
    OperationTemplate("teff_meher", "land_prep", -25, 10), OperationTemplate("teff_meher", "planting", 0, 7),
    OperationTemplate("teff_meher", "basal_fert", 0, 5), OperationTemplate("teff_meher", "weeding", 25, 7),
    OperationTemplate("teff_meher", "top_dress", 30, 7),
]
CODES = ["land_prep", "planting", "basal_fert", "weeding", "top_dress"]


def synthetic_households(seed: int = 11) -> list[Household]:
    rng = np.random.default_rng(seed)
    hh = []
    for i in range(260):
        k = KEBELES[i % 4]
        willing = {"teff_meher"} | ({"maize_meher"} if rng.random() < 0.7 else set())
        h = Household(f"HH-{i:04d}", k, willing)
        for j in range(rng.integers(1, 4)):
            area = float(np.round(rng.uniform(0.15, 0.9), 2))
            h.plots.append(HouseholdPlot(f"P-{i:04d}-{j}", h.household_id, k, area,
                                         {"teff_meher": float(rng.uniform(0.5, 1.0)), "maize_meher": float(rng.uniform(0.3, 1.0))}))
        hh.append(h)
    return hh


def simulate_reports(ops, seed: int = 3) -> list[FieldReport]:
    """Kebele 3 has poor road access in the rains: more delays. Top dressing often late (urea arrives late)."""
    rng = np.random.default_rng(seed)
    reps = []
    for op in ops:
        miss = 0.03 + (0.05 if op.kebele == "Kebele 3" else 0)
        if rng.random() < miss:
            reps.append(FieldReport(op.plot_id, op.code, None, "DA-1"))
            continue
        delay = rng.normal(0, 4) + (6 if op.kebele == "Kebele 3" else 0) + (5 if op.code == "top_dress" else 0)
        reps.append(FieldReport(op.plot_id, op.code, op.target + timedelta(days=int(round(delay))), "DA-1"))
    return reps


def main() -> int:
    try:
        hh = synthetic_households()
        assigns, gaps = assign_plots(hh, {"teff_meher": 180.0, "maize_meher": 120.0})
        area = Counter()
        for a in assigns:
            area[a.option_id] += a.area_ha
        print(f"== 1. {len(assigns)} plots assigned: " + ", ".join(f"{k} {v:.1f} ha" for k, v in area.items())
              + f" | gaps: {gaps} | households involved: {len({a.household_id for a in assigns})}")
        print(f"  [DEBUG] mean suitability of assigned plots: {np.mean([a.suitability for a in assigns]):.2f}")

        ops = build_calendar(assigns, TEMPLATES, PLANTING)
        print(f"\n== 2. {len(ops)} planned operations")
        weekly = defaultdict(Counter)
        for o in ops:
            wk = o.target - timedelta(days=o.target.weekday())
            weekly[wk][o.code] += 1

        reps = simulate_reports(ops)
        adh = adherence(ops, reps, as_of=date(2026, 8, 31))
        print("\n== 3. Adherence (on-time share) by operation:")
        for c in CODES:
            print(f"  {c:11s} {adh['code'][c]:.0%}")
        kebele_plant = [round(100 * adh["kebele_code"][(k, "planting")], 1) for k in KEBELES]
        kebele_top = [round(100 * adh["kebele_code"][(k, "top_dress")], 1) for k in KEBELES]
        for k, p, t in zip(KEBELES, kebele_plant, kebele_top):
            print(f"  {k}: planting {p:.0f}%  top dressing {t:.0f}%")

        visits = prioritise_visits(assigns, adh, {"teff_meher": 150_000, "maize_meher": 105_000}, capacity=12)
        print("\n== 4. This week's extension visits (top 12):")
        for v in visits[:5]:
            print(f"  {v.plot_id} {v.kebele} priority {v.priority:5.1f}  {', '.join(v.reasons)}")
        print(f"  [DEBUG] visits per kebele: {Counter(v.kebele for v in visits)}")

        weeks = sorted(weekly)
        out = {"kebeles": KEBELES, "planting": kebele_plant, "top_dress": kebele_top,
               "by_code": {c: round(100 * adh["code"][c], 1) for c in CODES},
               "weeks": [w.strftime("%d %b") for w in weeks],
               "workload": {c: [weekly[w][c] for w in weeks] for c in ["land_prep", "planting", "weeding", "top_dress"]},
               "assigned": {k: round(v, 1) for k, v in area.items()}, "plots": len(assigns),
               "households": len({a.household_id for a in assigns}),
               "visits": [{"plot_id": v.plot_id, "kebele": v.kebele, "priority": v.priority, "reasons": list(v.reasons)} for v in visits]}
        path = ROOT / "assets" / "demo-farm.json"
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

"""
Harvest scheduling, losses, drying, grading and lot formation.

  schedule            assign each plot to a resource-day. Policy "edf" (earliest window end first) or
                      "fifo" (order of requests). A plot takes ceil(area / capacity-left) partial days.
  field_loss_share    shattering and lodging losses grow with days past the window end
  dry_weight          weight after drying from moisture m0 to m1 (water balance: dry matter is conserved)
  grade_of            first grade whose limits the lot meets
  form_lots           group harvested plots by cluster, product, week into lots up to a maximum size
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

from .domain import GradeSpec, HarvestJob, HarvestLot, HarvestResource, MaturityWindow


def schedule(windows: list[MaturityWindow], resources: list[HarvestResource], policy: str = "edf") -> list[HarvestJob]:
    if policy not in ("edf", "fifo"):
        raise ValueError(f"Unknown policy {policy}")
    order = sorted(windows, key=lambda w: (w.ready_to, w.ready_from)) if policy == "edf" else list(windows)
    cap = {(r.resource_id, d): r.ha_per_day for r in resources for d in r.working_days}
    days = sorted({d for r in resources for d in r.working_days})
    jobs = []
    for w in order:
        need = w.area_ha
        last_day, chosen = None, None
        for d in (d for d in days if d >= w.ready_from):
            for r in resources:
                k = (r.resource_id, d)
                if cap.get(k, 0) > 1e-9:
                    take = min(need, cap[k])
                    cap[k] -= take
                    need -= take
                    last_day, chosen = d, r.resource_id
                    if need <= 1e-9:
                        break
            if need <= 1e-9:
                break
        if need > 1e-9:
            raise RuntimeError(f"Not enough harvest capacity for {w.plot_id}; add resources or working days")
        jobs.append(HarvestJob(w.plot_id, chosen, last_day, max(0, (last_day - w.ready_to).days)))
    return jobs


def field_loss_share(days_late: int, base: float = 0.03, per_day: float = 0.012, cap: float = 0.35) -> float:
    """Base handling loss plus shattering/lodging that grows each day past the window (teff shatters easily)."""
    if days_late < 0:
        raise ValueError("days_late must be >= 0")
    return min(cap, base + per_day * days_late)


def dry_weight(weight_kg: float, m0: float, m1: float) -> float:
    """Dry matter is conserved: W1 = W0 x (100 - m0) / (100 - m1)."""
    if not (0 <= m1 <= m0 < 100):
        raise ValueError(f"Need 0 <= target moisture <= initial moisture < 100, got {m0} -> {m1}")
    return weight_kg * (100 - m0) / (100 - m1)


def grade_of(moisture: float, foreign: float, specs: list[GradeSpec]) -> str:
    for g in specs:
        if moisture <= g.max_moisture and foreign <= g.max_foreign:
            return g.grade
    return "below grade"


def form_lots(harvested: list[dict], max_lot_kg: float = 10_000, segregate_by: str | None = None) -> list[HarvestLot]:
    """
    harvested: [{plot_id, cluster_id, product, day, kg, moisture, foreign, ...}] -> lots with traceability.
    `segregate_by` keeps grain with different handling (e.g. tarpaulin vs bare-ground threshing) in separate
    lots, so clean grain is not downgraded by mixing.
    """
    groups = defaultdict(list)
    for h in harvested:
        wk = h["day"].isocalendar()
        seg = str(h.get(segregate_by, "")) if segregate_by else ""
        groups[(h["cluster_id"], h["product"], f"{wk[0]}-W{wk[1]:02d}", seg)].append(h)
    lots = []
    for (cl, prod, week, _seg), items in sorted(groups.items()):
        cur = None
        for h in sorted(items, key=lambda x: x["plot_id"]):
            if cur is None or cur.weight_kg + h["kg"] > max_lot_kg:
                cur = HarvestLot(f"LOT-{cl}-{prod[:4].upper()}-{week}-{len([l for l in lots if l.cluster_id == cl]) + 1:03d}", cl, prod, week)
                lots.append(cur)
            w0 = cur.weight_kg
            cur.weight_kg += h["kg"]
            cur.moisture = (cur.moisture * w0 + h["moisture"] * h["kg"]) / cur.weight_kg
            cur.foreign = (cur.foreign * w0 + h["foreign"] * h["kg"]) / cur.weight_kg
            cur.plot_ids.append(h["plot_id"])
    return lots


def days_needed(area_ha: float, ha_per_day: float) -> int:
    return math.ceil(area_ha / ha_per_day)

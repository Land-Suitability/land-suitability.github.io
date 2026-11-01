"""
Input requirements, supplier allocation and backward scheduling.

  explode_plan          production plan allocations x input norms -> dated requirements
  p_on_time             P(lead time <= days available) for a lognormal lead time
  order_by_date         latest order date that meets a target on-time probability
  allocate              split each requirement across suppliers: most reliable first (shortest P90 lead
                        time), then cheapest, within remaining capacity; produces dated purchase orders
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from .domain import InputNorm, InputRequirement, PurchaseOrder, Supplier


def explode_plan(allocations: list[dict], norms: list[InputNorm], planting: dict[str, date]) -> list[InputRequirement]:
    """allocations: [{cluster_id, option_id, hectares}] as produced by stage 04."""
    reqs = []
    for a in allocations:
        if a["option_id"] not in planting:
            raise KeyError(f"No planting date for option {a['option_id']}")
        for n in (n for n in norms if n.option_id == a["option_id"]):
            qty = a["hectares"] * n.rate_per_ha * n.applies_share
            if qty > 0:
                need = planting[a["option_id"]] + timedelta(days=n.days_from_planting)
                reqs.append(InputRequirement(a["cluster_id"], n.item, qty, need, a["option_id"]))
    return reqs


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def p_on_time(s: Supplier, days_available: float) -> float:
    if days_available <= 0:
        return 0.0
    if s.lead_spread == 0:
        return 1.0 if days_available >= s.lead_median_days else 0.0
    return _norm_cdf((math.log(days_available) - math.log(s.lead_median_days)) / s.lead_spread)


def lead_quantile(s: Supplier, q: float) -> float:
    if not 0 < q < 1:
        raise ValueError("q must be in (0, 1)")
    # inverse normal by bisection (keeps the module dependency-free)
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _norm_cdf(mid) < q else (lo, mid)
    return s.lead_median_days * math.exp(s.lead_spread * (lo + hi) / 2)


def order_by_date(s: Supplier, need_by: date, target: float = 0.9) -> date:
    return need_by - timedelta(days=math.ceil(lead_quantile(s, target)))


def allocate(reqs: list[InputRequirement], suppliers: list[Supplier], target: float = 0.9,
             today: date | None = None) -> tuple[list[PurchaseOrder], list[str]]:
    """Returns purchase orders and a list of warnings (shortfalls, orders already late)."""
    remaining = {s.supplier_id: dict(s.capacity) for s in suppliers}
    orders, warnings = [], []
    for r in sorted(reqs, key=lambda r: r.need_by):
        cands = [s for s in suppliers if r.item.code in s.items]
        if not cands:
            warnings.append(f"No supplier for {r.item.code} ({r.cluster_id})")
            continue
        cands.sort(key=lambda s: (lead_quantile(s, target), s.price.get(r.item.code, math.inf)))
        left = r.quantity
        for s in cands:
            cap = remaining[s.supplier_id].get(r.item.code, 0.0)
            take = min(left, cap)
            if take <= 1e-9:
                continue
            remaining[s.supplier_id][r.item.code] = cap - take
            ob = order_by_date(s, r.need_by, target)
            if today and ob < today:
                days = (r.need_by - today).days
                warnings.append(f"{r.item.code} for {r.cluster_id}: order date passed; P(on time) now {p_on_time(s, days):.0%}")
            orders.append(PurchaseOrder(s.supplier_id, r.cluster_id, r.item.code, take, r.need_by, ob,
                                        p_on_time(s, (r.need_by - ob).days), take * s.price.get(r.item.code, 0.0)))
            left -= take
            if left <= 1e-9:
                break
        if left > 1e-6:
            warnings.append(f"Shortfall {left:,.0f} {r.item.unit} of {r.item.code} for {r.cluster_id}")
    return orders, warnings

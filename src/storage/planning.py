"""
Where to aggregate, how long to store, and whether the stores are big enough.

  locate_centres        capacitated p-median heuristic: greedy addition, then 1-for-1 swaps (Teitz-Bart)
                        to minimise tonne-km from supply points to their nearest centre with capacity
  store_or_sell         net value per tonne of selling after m months, given the seasonal price index
                        (stage 05), monthly storage loss and cost, and the farmers' cost of waiting (interest)
  simulate_inventory    weekly stock from inflows and outflows; flags weeks over capacity
"""
from __future__ import annotations

import itertools
import math

import numpy as np

from .domain import CandidateSite, CollectionCentre, StorageTech, SupplyPoint


def _dist(a, b) -> float:
    return math.hypot(a.x_km - b.x_km, a.y_km - b.y_km) * 1.3     # road detour factor over straight line


def assign(points: list[SupplyPoint], sites: list[CandidateSite]) -> tuple[float, dict[str, list[str]]]:
    """Largest supply first to its nearest site with capacity left. Returns (tonne-km, site -> points)."""
    left = {s.site_id: s.capacity_t for s in sites}
    served = {s.site_id: [] for s in sites}
    cost = 0.0
    for p in sorted(points, key=lambda p: -p.tonnes):
        for s in sorted(sites, key=lambda s: _dist(p, s)):
            if left[s.site_id] >= p.tonnes:
                left[s.site_id] -= p.tonnes
                served[s.site_id].append(p.point_id)
                cost += p.tonnes * _dist(p, s)
                break
        else:
            return math.inf, served
    return cost, served


def locate_centres(points: list[SupplyPoint], candidates: list[CandidateSite], p: int) -> tuple[list[CollectionCentre], float]:
    if not 1 <= p <= len(candidates):
        raise ValueError(f"p must be between 1 and {len(candidates)}")
    chosen: list[CandidateSite] = []
    for _ in range(p):                                   # greedy addition
        best = min((c for c in candidates if c not in chosen), key=lambda c: assign(points, chosen + [c])[0])
        chosen.append(best)
    best_cost = assign(points, chosen)[0]
    improved = True
    while improved:                                      # 1-for-1 swaps
        improved = False
        for i, out_site in itertools.product(range(len(chosen)), [c for c in candidates if c not in chosen]):
            trial = chosen[:i] + [out_site] + chosen[i + 1:]
            cost = assign(points, trial)[0]
            if cost < best_cost - 1e-6:
                chosen, best_cost, improved = trial, cost, True
                break
    if math.isinf(best_cost):
        raise RuntimeError(f"{p} centres do not have enough capacity for {sum(p.tonnes for p in points):,.0f} t")
    _, served = assign(points, chosen)
    tonnes = {p.point_id: p.tonnes for p in points}
    return [CollectionCentre(s, served[s.site_id], sum(tonnes[q] for q in served[s.site_id])) for s in chosen], best_cost


def store_or_sell(price_index: list[float], harvest_month: int, tech: StorageTech, base_price: float,
                  interest_per_month: float = 0.015, inflation_per_month: float = 0.011, months: int = 8) -> list[float]:
    """
    Net birr per tonne stored at harvest if sold m = 0..months later:
        price(m) x (1 - loss)^m - cost x m, discounted by the farmers' cost of waiting (interest).
    price(m) = base x seasonal index ratio x general inflation (stage 05 trend, ~14%/year = ~1.1%/month).
    price_index: 12 seasonal factors (January first) from stage 05.
    """
    if len(price_index) != 12 or not 1 <= harvest_month <= 12:
        raise ValueError("Need a 12-month price index and a harvest month 1..12")
    h = harvest_month - 1
    out = []
    for m in range(months + 1):
        price = base_price * price_index[(h + m) % 12] / price_index[h] * (1 + inflation_per_month) ** m
        value = price * (1 - tech.loss_per_month) ** m - tech.cost_birr_t_month * m
        out.append(value / (1 + interest_per_month) ** m)
    return out


def simulate_inventory(inflow_t: list[float], outflow_t: list[float], capacity_t: float) -> tuple[np.ndarray, list[int]]:
    if len(inflow_t) != len(outflow_t):
        raise ValueError("inflow and outflow must cover the same weeks")
    stock, level = [], 0.0
    for i, o in zip(inflow_t, outflow_t):
        level = max(0.0, level + i - o)
        stock.append(level)
    s = np.array(stock)
    return s, [int(w) for w in np.where(s > capacity_t)[0]]

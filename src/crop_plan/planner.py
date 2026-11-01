"""
Market-backwards production planner (linear programme, solved with HiGHS via scipy).

Decision variables   x[c, o] = hectares of crop option o in cluster c
Objective            maximise expected farmer net income
                       expected yield = potential x suitability x (fit + (1 - fit) x failure share)
Constraints
  land        per cluster and season:    sum_o x[c, o]                         <= area[c, season]
  water       per cluster and MONTH:     sum_o water[o, m] x[c, o]            <= supply[c, m]   (stage 02)
  demand      per product:   min_t <=    sum_c,o expected_t[c, o] x[c, o]     <= max_t          (stage 05)
  food        per cluster:               sum_teff x[c, o]  >= share x Meher area
  rotation    per cluster and season:    sum_product x[c, o] <= share x season area
Unsuitable options (suitability 0) are fixed to 0 ha.

The dual values (shadow prices) of these constraints tell planners and investors what binds:
the extra income one more m3 of water in a month, one more hectare, or one more tonne of demand
would bring.
"""
from __future__ import annotations

import numpy as np

from .domain import (ClusterProfile, CropOption, DemandSignal, PlanAllocation, PlanningPolicy, SeasonalProductionPlan,
                     ShadowPrice)

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class InfeasiblePlan(RuntimeError):
    """Raised when no plan can satisfy the hard constraints (e.g. contracts exceed capacity)."""


def expected_yield(opt: CropOption, cl: ClusterProfile) -> float:
    s = cl.suitability.get(opt.option_id, 0.0)
    fit = cl.cycle_fit.get(opt.option_id, 1.0)
    return opt.potential_yield_t_ha * s * (fit + (1 - fit) * opt.failure_yield_share)


def plan(clusters: list[ClusterProfile], options: list[CropOption], demand: list[DemandSignal],
         policy: PlanningPolicy | None = None, plan_id: str = "PLAN-DEMO") -> SeasonalProductionPlan:
    try:
        from scipy.optimize import linprog
    except ImportError as e:
        raise ImportError("The planner needs scipy (pip install scipy)") from e
    policy = policy or PlanningPolicy()
    if not clusters or not options:
        raise ValueError("Need at least one cluster and one crop option")
    price = {d.product: d.price_birr_t for d in demand if d.price_birr_t}
    idx = [(c, o) for c in clusters for o in options]
    n = len(idx)
    ey = np.array([expected_yield(o, c) for c, o in idx])
    pr = np.array([price.get(o.product, o.price_birr_t) for _, o in idx])
    cost = np.array([o.cost_birr_ha for _, o in idx])
    margin = ey * pr - cost

    rows, rhs, names = [], [], []

    def add(row, b, name):
        rows.append(row); rhs.append(b); names.append(name)

    for c in clusters:
        for season in ("meher", "dry"):
            row = np.array([1.0 if (cc is c and o.season == season) else 0.0 for cc, o in idx])
            if row.any():
                add(row, c.area_ha.get(season, 0.0), f"land {c.cluster_id} {season}")
        for m in range(12):
            row = np.array([o.water_m3_ha[m] if cc is c else 0.0 for cc, o in idx])
            if row.any():
                add(row, c.water_m3[m], f"water {c.cluster_id} {MONTHS[m]}")
        for product, share in policy.food_security.items():       # -sum_product + share*sum_meher <= 0
            row = np.array([(-1.0 if o.product == product else 0.0) + share if (cc is c and o.season == "meher") else 0.0
                            for cc, o in idx])
            add(row, 0.0, f"food {c.cluster_id} {product}")
        for product, share in policy.max_share.items():
            for season in ("meher", "dry"):
                row = np.array([((1.0 if o.product == product else 0.0) - share) if (cc is c and o.season == season) else 0.0
                                for cc, o in idx])
                if np.any(row > 0):
                    add(row, 0.0, f"rotation {c.cluster_id} {season} {product}")
    for d in demand:
        row = np.array([ey[k] if o.product == d.product else 0.0 for k, (_, o) in enumerate(idx)])
        add(row, d.max_t, f"demand max {d.product}")
        if d.min_t > 0:
            add(-row, -d.min_t, f"demand min {d.product}")

    bounds = [(0, 0) if c.suitability.get(o.option_id, 0.0) <= 0 else (0, None) for c, o in idx]
    res = linprog(-margin, A_ub=np.array(rows), b_ub=np.array(rhs), bounds=bounds, method="highs")
    if res.status == 2:
        raise InfeasiblePlan("No feasible plan: contracted minimums exceed what land and water can produce")
    if not res.success:
        raise RuntimeError(f"Solver failed: {res.message}")

    x = res.x
    allocs = tuple(PlanAllocation(c.cluster_id, o.option_id, o.product, o.season, float(x[k]), float(x[k] * ey[k]),
                                  float(x[k] * margin[k])) for k, (c, o) in enumerate(idx) if x[k] > 1e-6)
    tonnes: dict[str, float] = {}
    for a in allocs:
        tonnes[a.product] = tonnes.get(a.product, 0.0) + a.expected_t
    duals = -res.ineqlin.marginals            # HiGHS marginals are for the minimisation; flip sign
    binding = tuple(sorted((ShadowPrice(nm, float(v)) for nm, v in zip(names, duals) if abs(v) > 1e-6),
                           key=lambda s: -abs(s.value_birr)))
    return SeasonalProductionPlan(plan_id, allocs, float(-res.fun), tonnes, binding)

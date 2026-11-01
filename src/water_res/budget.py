"""
Water budget for a planning cluster: sustainable supply versus irrigation demand, month by month.

The key output for stage 04 is not one seasonal number but monthly limits:
    sum over crops of (hectares x demand per ha in month m)  <=  supply in month m   for every m
A seasonal total hides the peak month; the peak month is usually what binds.
"""
from __future__ import annotations

import numpy as np

from .domain import ClusterWaterContext, Confidence, IrrigatedCropPlan, MonthlySeries, WaterBudget
from .hydrology import et0_hargreaves, irrigation_demand

_ORDER = [Confidence.INDICATIVE, Confidence.MODELLED, Confidence.MEASURED]


def total_supply(ctx: ClusterWaterContext) -> np.ndarray:
    if not ctx.sources:
        raise ValueError(f"Cluster {ctx.cluster_id} has no water sources")
    return np.sum([np.array(s.sustainable_monthly_m3()) for s in ctx.sources], axis=0)


def build_budget(ctx: ClusterWaterContext, plans: list[IrrigatedCropPlan], tmin: MonthlySeries,
                 tmax: MonthlySeries, rain: MonthlySeries, season: str = "dry") -> WaterBudget:
    supply = total_supply(ctx)
    et0 = et0_hargreaves(ctx.latitude_deg, tmin, tmax)
    demand, binding, max_area = {}, {}, {}
    for plan in plans:
        d = irrigation_demand(plan, et0, rain)["gross_m3"]
        name = plan.crop.crop
        demand[name] = tuple(float(x) for x in d)
        active = d > 1e-9
        if not active.any():
            binding[name], max_area[name] = -1, float(ctx.irrigable_area_ha)
            continue
        ratio = np.full(12, np.inf)
        ratio[active] = supply[active] / d[active]        # ha supportable in each month
        m = int(np.argmin(ratio))
        binding[name] = m
        max_area[name] = float(min(ratio[m], ctx.irrigable_area_ha))
    confidence = min((s.confidence for s in ctx.sources), key=_ORDER.index)   # weakest link
    return WaterBudget(cluster_id=ctx.cluster_id, season=season, supply_m3=tuple(float(x) for x in supply),
                       demand_m3_per_ha=demand, binding_month=binding, max_area_ha=max_area,
                       seasonal_supply_m3=float(supply.sum()), confidence=confidence)


def check_allocation(budget: WaterBudget, hectares: dict[str, float]) -> dict:
    """Test a proposed crop mix (ha per crop) against the monthly supply."""
    unknown = set(hectares) - set(budget.demand_m3_per_ha)
    if unknown:
        raise KeyError(f"No demand computed for crops: {sorted(unknown)}")
    use = np.zeros(12)
    for crop, ha in hectares.items():
        if ha < 0:
            raise ValueError(f"Negative area for {crop}")
        use += ha * np.array(budget.demand_m3_per_ha[crop])
    supply = np.array(budget.supply_m3)
    balance = supply - use
    return {"use_m3": use, "balance_m3": balance, "feasible": bool(np.all(balance >= -1e-6)),
            "deficit_months": [int(m) for m in np.where(balance < -1e-6)[0]]}

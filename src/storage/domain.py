"""
Domain model for Stage 10: Storage, Processing & Aggregation.

Ubiquitous language
-------------------
SupplyPoint        A kebele (or village) with expected tonnes to aggregate (stages 08, 09).
CandidateSite      A possible collection centre: location, capacity, fixed cost (existing cooperative stores first).
CollectionCentre   A chosen site with the supply points it serves.
StorageTech        How grain is kept: traditional bags, hermetic bags, warehouse with fumigation; each has a
                   monthly loss rate and a cost per tonne per month.
WarehouseReceipt   A record that a farmer group owns a graded lot in store, so it can sell later (or borrow
                   against it) instead of selling at the harvest-time price low.
StockMovement      A lot in or out of a centre in a given week.

Analogy
-------
A savings account for grain. Selling at harvest is like cashing in at the worst exchange rate. Storing is
saving: the price usually rises through the lean season (interest), but pests and moisture eat part of the
grain (fees). Hermetic bags are the account with low fees, so saving pays for longer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class SupplyPoint:
    point_id: str
    x_km: float
    y_km: float
    tonnes: float


@dataclass(frozen=True)
class CandidateSite:
    site_id: str
    x_km: float
    y_km: float
    capacity_t: float
    fixed_cost_birr: float
    existing: bool = False


@dataclass
class CollectionCentre:
    site: CandidateSite
    served: list[str] = field(default_factory=list)
    tonnes: float = 0.0


@dataclass(frozen=True)
class StorageTech:
    name: str
    loss_per_month: float          # share of weight lost to insects, moulds, rodents
    cost_birr_t_month: float       # bags, fumigation, warehouse fee


@dataclass(frozen=True)
class WarehouseReceipt:
    receipt_id: str
    lot_id: str                    # from stage 09
    owner_group: str               # cooperative or farmer group (pseudonymous)
    product: str
    grade: str
    weight_kg: float
    deposited: date
    centre_id: str


@dataclass(frozen=True)
class StockMovement:
    centre_id: str
    week: int
    lot_id: str
    tonnes: float                  # positive in, negative out

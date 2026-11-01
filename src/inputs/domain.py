"""
Domain model for Stage 06: Input & Resource Coordination.

Ubiquitous language
-------------------
InputItem          Seed of a variety, fertilizer (NPS, urea), lime, crop protection, irrigation kit.
InputNorm          How much of an item one hectare of a crop option needs, and when (days from planting).
Supplier           Cooperative union, seed enterprise or agro-dealer, with capacity, price and an UNCERTAIN
                   lead time (median days and spread).
InputRequirement   Item, quantity, cluster and need-by date, exploded from the production plan (stage 04).
PurchaseOrder      Supplier, item, quantity, order-by date and the probability of arriving on time.

Analogy
-------
Cooking a holiday meal backwards from the time guests arrive: the roast needs three hours, so it goes in
at three; the butcher needs two days' notice, so you call him on Thursday. Here, planting day is the guests
arriving, and every input is ordered early enough that it arrives on time in 9 cases out of 10.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class InputItem:
    code: str               # "seed_teff", "nps", "urea", "lime"
    name: str
    unit: str               # "kg", "t"


@dataclass(frozen=True)
class InputNorm:
    option_id: str          # crop option from stage 04
    item: InputItem
    rate_per_ha: float
    days_from_planting: int = -7       # negative = before planting (basal), positive = top dressing
    applies_share: float = 1.0         # e.g. lime only on the share of area with acidic soils (stage 01)
    note: str = "indicative; follow regional recommendations"


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    kind: str                        # "cooperative_union", "seed_enterprise", "agro_dealer"
    items: tuple[str, ...]
    capacity: dict                   # item code -> max quantity per season
    price: dict                      # item code -> birr per unit
    lead_median_days: float
    lead_spread: float               # lognormal sigma (0.3 = moderately unpredictable)

    def __post_init__(self) -> None:
        if self.lead_median_days <= 0 or self.lead_spread < 0:
            raise ValueError(f"{self.supplier_id}: invalid lead time parameters")


@dataclass(frozen=True)
class InputRequirement:
    cluster_id: str
    item: InputItem
    quantity: float
    need_by: date
    source_option: str


@dataclass(frozen=True)
class PurchaseOrder:
    supplier_id: str
    cluster_id: str
    item_code: str
    quantity: float
    need_by: date
    order_by: date
    p_on_time: float                 # probability delivery arrives by need_by if ordered on order_by
    cost_birr: float

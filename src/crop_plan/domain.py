"""
Domain model for Stage 04: Crop Selection & Production Planning.

Ubiquitous language
-------------------
CropOption        A crop + variety + season combination a cluster could grow (e.g. rainfed teff in Meher,
                  irrigated wheat in the dry season), with its economics and water curve.
ClusterProfile    What one planning cluster offers: area per season, suitability per crop (stage 01),
                  monthly water (stage 02) and crop-cycle fit (stage 03).
DemandSignal      What buyers will take (stage 05): crop product, minimum and maximum tonnes, price.
PlanningPolicy    Rules the plan must respect: food-security share, rotation caps.
SeasonalProductionPlan
                  The aggregate root: allocations (cluster x option x hectares), expected tonnes and income,
                  and the shadow prices that explain which limits bind.

Analogy
-------
A restaurant kitchen planning next week's menu from its reservation book (demand), its pantry
(land and water) and its cooks' skills (suitability). The plan is the menu; the shadow prices are the
manager's note saying "one more litre of milk on Tuesday would have earned us 40 birr".
"""
from __future__ import annotations

from dataclasses import dataclass, field

SEASONS = ("meher", "dry")


@dataclass(frozen=True)
class CropOption:
    option_id: str
    product: str                    # what buyers buy: "wheat", "teff", "maize", "onion"
    season: str                     # "meher" (rainfed) or "dry" (irrigated)
    cycle_days: int
    potential_yield_t_ha: float     # at S1 with recommended inputs
    price_birr_t: float             # farm-gate reference price (stage 05)
    cost_birr_ha: float             # inputs, labour, irrigation energy
    water_m3_ha: tuple[float, ...] = (0.0,) * 12   # gross irrigation demand per month (stage 02)
    failure_yield_share: float = 0.5               # yield kept if the season is too short for the cycle

    def __post_init__(self) -> None:
        if self.season not in SEASONS:
            raise ValueError(f"{self.option_id}: unknown season {self.season}")
        if len(self.water_m3_ha) != 12:
            raise ValueError(f"{self.option_id}: water curve needs 12 months")
        if self.potential_yield_t_ha <= 0 or self.price_birr_t <= 0:
            raise ValueError(f"{self.option_id}: yield and price must be positive")


@dataclass(frozen=True)
class ClusterProfile:
    cluster_id: str
    area_ha: dict[str, float]                  # season -> available hectares
    suitability: dict[str, float]              # option_id -> 0..1 yield factor (stage 01 score)
    cycle_fit: dict[str, float]                # option_id -> P(season long enough) (stage 03)
    water_m3: tuple[float, ...] = (0.0,) * 12  # sustainable monthly supply (stage 02)


@dataclass(frozen=True)
class DemandSignal:
    product: str
    min_t: float                               # contracted minimum (must deliver)
    max_t: float                               # buyers will not take more
    price_birr_t: float | None = None          # contract price overrides the reference price


@dataclass(frozen=True)
class PlanningPolicy:
    food_security: dict[str, float] = field(default_factory=dict)   # product -> min share of Meher area
    max_share: dict[str, float] = field(default_factory=dict)       # product -> max share of season area


@dataclass(frozen=True)
class PlanAllocation:
    cluster_id: str
    option_id: str
    product: str
    season: str
    hectares: float
    expected_t: float
    expected_net_birr: float


@dataclass(frozen=True)
class ShadowPrice:
    constraint: str            # e.g. "water B Feb", "land A meher", "demand max wheat"
    value_birr: float          # extra income from one more unit (m3, ha or tonne)


@dataclass(frozen=True)
class SeasonalProductionPlan:
    plan_id: str
    allocations: tuple[PlanAllocation, ...]
    total_net_birr: float
    tonnes_by_product: dict[str, float]
    binding: tuple[ShadowPrice, ...]

    def hectares(self, cluster_id: str, option_id: str) -> float:
        return sum(a.hectares for a in self.allocations if a.cluster_id == cluster_id and a.option_id == option_id)

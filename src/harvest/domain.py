"""
Domain model for Stage 09: Harvest & Post-harvest Management.

Ubiquitous language
-------------------
MaturityWindow   When a plot is ready: from the first good day to the last day before losses climb
                 (from stage 08 senescence and stage 07 planting dates).
HarvestResource  A thresher, combine or labour crew with a daily capacity (ha/day) and working days.
HarvestJob       A plot scheduled on a day with a resource.
GradeSpec        Buyer grade limits: maximum moisture and foreign matter (from stage 05 contracts).
HarvestLot       The traceable unit: a lot ID that lists its plots, weight, moisture, grade and date.
                 Every bag in storage (10), on a truck (11) and at the buyer (12) points back to a lot.
LossRecord       Kilograms lost per step: field (late harvest, shattering), threshing, drying, handling.

Analogy
-------
An airport with few runways (threshers) and many planes (plots) whose fuel is running low (maturity
windows closing). The controller lands the plane with the least fuel left first, not the one that called
first. That simple rule, earliest deadline first, is what cuts field losses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class MaturityWindow:
    plot_id: str
    cluster_id: str
    product: str
    area_ha: float
    expected_t: float
    ready_from: date
    ready_to: date          # after this, losses rise quickly

    def __post_init__(self) -> None:
        if self.ready_to < self.ready_from:
            raise ValueError(f"{self.plot_id}: window ends before it starts")


@dataclass(frozen=True)
class HarvestResource:
    resource_id: str
    kind: str               # "thresher", "combine", "crew"
    ha_per_day: float
    working_days: tuple[date, ...]


@dataclass(frozen=True)
class HarvestJob:
    plot_id: str
    resource_id: str
    day: date
    days_late: int          # days after ready_to (0 = inside the window)


@dataclass(frozen=True)
class GradeSpec:
    grade: str
    max_moisture: float     # %
    max_foreign: float      # %


@dataclass
class HarvestLot:
    lot_id: str
    cluster_id: str
    product: str
    harvest_week: str
    plot_ids: list[str] = field(default_factory=list)
    weight_kg: float = 0.0
    moisture: float = 0.0
    foreign: float = 0.0
    grade: str = "ungraded"


@dataclass(frozen=True)
class LossRecord:
    step: str               # "field", "threshing", "drying", "handling"
    kg: float

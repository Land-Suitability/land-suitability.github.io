"""
Domain model for Stage 02: Water Resource Assessment.

Ubiquitous language
-------------------
WaterSource        A physical source a cluster can draw from: river diversion, shallow wells,
                   borehole, pond/reservoir, or rain (for rainfed crops).
SustainableSupply  What a source can give month by month WITHOUT harming the river, the aquifer
                   or downstream users (environmental flow and recharge limits applied).
CropWaterNeed      Crop water requirement for one crop/season, from ET0 x Kc minus effective rain.
IrrigationDemand   Gross water to abstract = net requirement / application efficiency, per month.
WaterBudget        For one PlanningCluster and season: monthly supply, monthly demand per crop,
                   balance, binding month and maximum irrigable area per crop.

Analogy
-------
A household budget with a salary paid unevenly through the year. The annual total may look
fine, but what matters is whether there is enough money in the leanest month. Water is the
same: the dry-season peak month, not the seasonal total, usually decides how many hectares
can be irrigated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class SourceType(str, Enum):
    RIVER_DIVERSION = "river_diversion"
    SHALLOW_WELLS = "shallow_wells"       # hand-dug wells, typical on lake-shore plains
    BOREHOLE = "borehole"
    POND_RESERVOIR = "pond_reservoir"     # micro-dams, ponds, small reservoirs


class Confidence(str, Enum):
    """How well a supply estimate is known. Satellite-only estimates are never 'measured'."""
    MEASURED = "measured"        # gauged flow, pumping test
    MODELLED = "modelled"        # hydrological model calibrated on local data
    INDICATIVE = "indicative"    # regional coefficients, remote sensing only


class Method(str, Enum):
    FURROW = "furrow"
    BASIN = "basin"
    SPRINKLER = "sprinkler"
    DRIP = "drip"

    @property
    def efficiency(self) -> float:
        """Typical application efficiencies (FAO guidance ranges, mid values)."""
        return {"furrow": 0.60, "basin": 0.60, "sprinkler": 0.75, "drip": 0.90}[self.value]


# ------------------------------------------------------------------ value objects
@dataclass(frozen=True)
class MonthlySeries:
    """Twelve monthly values, January first. Validated on creation."""
    values: tuple[float, ...]
    unit: str

    def __post_init__(self) -> None:
        if len(self.values) != 12:
            raise ValueError(f"MonthlySeries needs 12 values, got {len(self.values)}")
        if any(v != v for v in self.values):  # NaN check without numpy
            raise ValueError("MonthlySeries contains NaN")

    def __getitem__(self, i: int) -> float:
        return self.values[i]


@dataclass(frozen=True)
class CropCoefficients:
    """FAO-56 single crop coefficient curve and stage lengths (days)."""
    crop: str
    kc_ini: float
    kc_mid: float
    kc_end: float
    l_ini: int
    l_dev: int
    l_mid: int
    l_late: int
    note: str = "FAO-56 typical values; adjust to local varieties"

    @property
    def season_days(self) -> int:
        return self.l_ini + self.l_dev + self.l_mid + self.l_late


@dataclass(frozen=True)
class IrrigatedCropPlan:
    crop: CropCoefficients
    planting_month: int          # 1..12
    planting_day: int = 1
    method: Method = Method.FURROW


# ------------------------------------------------------------------ entities
@dataclass
class WaterSource:
    source_id: str
    kind: SourceType
    name: str
    confidence: Confidence
    # monthly volume the physical source provides (m3), before sustainability limits
    gross_monthly_m3: MonthlySeries | None = None
    # rules that turn gross into sustainable supply
    environmental_flow_fraction: float = 0.0   # share of river flow that must stay in the river
    recharge_share: float = 1.0                # share of annual recharge that may be abstracted
    annual_recharge_m3: float | None = None    # groundwater only
    pump_capacity_m3_per_month: float | None = None  # infrastructure limit, if any

    def sustainable_monthly_m3(self) -> tuple[float, ...]:
        if self.kind in (SourceType.SHALLOW_WELLS, SourceType.BOREHOLE):
            if self.annual_recharge_m3 is None:
                raise ValueError(f"{self.source_id}: groundwater source needs annual_recharge_m3 "
                                 "(from field hydrogeology, not satellite data alone)")
            per_month = self.annual_recharge_m3 * self.recharge_share / 12.0
            out = [per_month] * 12
        else:
            if self.gross_monthly_m3 is None:
                raise ValueError(f"{self.source_id}: surface source needs gross_monthly_m3")
            keep = 1.0 - self.environmental_flow_fraction
            out = [v * keep for v in self.gross_monthly_m3.values]
        if self.pump_capacity_m3_per_month is not None:
            out = [min(v, self.pump_capacity_m3_per_month) for v in out]
        return tuple(out)


@dataclass
class ClusterWaterContext:
    cluster_id: str
    latitude_deg: float
    altitude_m: float
    irrigable_area_ha: float                    # land suitable for irrigation (from stage 01)
    sources: list[WaterSource] = field(default_factory=list)


@dataclass(frozen=True)
class WaterBudget:
    """Output contract to stage 04: monthly limits, not only a seasonal total."""
    cluster_id: str
    season: str
    supply_m3: tuple[float, ...]                 # sustainable, all sources, per month
    demand_m3_per_ha: dict[str, tuple[float, ...]]   # gross irrigation demand per crop per month
    binding_month: dict[str, int]                # month index that limits each crop alone
    max_area_ha: dict[str, float]                # max irrigable ha per crop if grown alone
    seasonal_supply_m3: float
    confidence: Confidence

"""
Domain model for Stage 05: Market Intelligence & Demand Forecasting.

Ubiquitous language
-------------------
Buyer             An off-taker: flour mill, processor, wholesaler, exporter, institution (school feeding,
                  hospitals). Identified by type and ID; commercial terms are confidential.
PriceObservation  A price for one product in one market in one month (birr per tonne).
PriceForecast     Expected harvest-time price with a prediction interval.
OfftakeContract   A pre-season agreement: product, volume, grade, delivery window and a PRICE RULE.
PriceRule         fixed | band (floor and ceiling around the market price) | spot.
DemandSignal      What stage 04 needs: product, contracted minimum, absorbable maximum, planning price.

Analogy
-------
A pre-season contract is like booking a hotel room: a fixed price protects you if prices rise, but if
prices fall sharply you are tempted to cancel; if they rise, the hotel is tempted to resell the room.
A price band (floor and ceiling) keeps both sides close enough to the market that neither walks away.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BuyerType(str, Enum):
    FLOUR_MILL = "flour_mill"
    PROCESSOR = "processor"
    WHOLESALER = "wholesaler"
    EXPORTER = "exporter"
    INSTITUTION = "institution"
    UNION = "cooperative_union"


class RuleKind(str, Enum):
    FIXED = "fixed"
    BAND = "band"
    SPOT = "spot"


@dataclass(frozen=True)
class Buyer:
    buyer_id: str
    kind: BuyerType
    location: str


@dataclass(frozen=True)
class PriceObservation:
    market: str
    product: str
    year: int
    month: int                     # 1..12
    price_birr_t: float

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12 or self.price_birr_t <= 0:
            raise ValueError(f"Invalid price observation: {self}")


@dataclass(frozen=True)
class PriceRule:
    kind: RuleKind
    fixed_price: float | None = None     # for FIXED
    floor: float | None = None           # for BAND
    ceiling: float | None = None         # for BAND

    def __post_init__(self) -> None:
        if self.kind == RuleKind.FIXED and not self.fixed_price:
            raise ValueError("FIXED rule needs fixed_price")
        if self.kind == RuleKind.BAND and not (self.floor and self.ceiling and self.floor < self.ceiling):
            raise ValueError("BAND rule needs floor < ceiling")

    def price(self, market_price):
        """Contract price given the market price at delivery (works on numpy arrays too)."""
        import numpy as np
        m = np.asarray(market_price, dtype=float)
        if self.kind == RuleKind.FIXED:
            return np.full_like(m, self.fixed_price)
        if self.kind == RuleKind.BAND:
            return np.clip(m, self.floor, self.ceiling)
        return m


@dataclass(frozen=True)
class OfftakeContract:
    contract_id: str
    buyer: Buyer
    product: str
    volume_t: float
    grade: str
    delivery_month: int
    rule: PriceRule
    advance_share: float = 0.0           # share of value paid before planting (reduces side-selling)


@dataclass(frozen=True)
class PriceForecast:
    product: str
    market: str
    year: int
    month: int
    median: float
    low80: float
    high80: float


@dataclass(frozen=True)
class DemandSignal:
    """Output contract to stage 04 (same shape as crop_plan.DemandSignal)."""
    product: str
    min_t: float
    max_t: float
    price_birr_t: float

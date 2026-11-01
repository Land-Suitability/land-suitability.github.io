"""
Domain model for Stage 01: Land Intelligence & Suitability.

Ubiquitous language
-------------------
Plot               A single parcel a household holds use rights to (land-use certificate).
PlanningCluster    A group of neighbouring plots planned together (the unit the market sees).
LandFactor         A measurable land quality (slope, pH, rainfall, ...).
FactorObservation  A value of one LandFactor at one place, with its source and uncertainty.
CropRequirement    For one crop and one factor, the ranges that make land S1 / S2 / S3 / N.
SuitabilityClass   FAO classes: S1 highly, S2 moderately, S3 marginally suitable, N not suitable.
SuitabilityAssessment
                   The result for (plot or cell) x crop x season: class, score, limiting factors,
                   uncertainty and the method/model version that produced it.

Design notes
------------
* Value objects are frozen dataclasses: they are compared by value and never mutated.
* Assessments always record *why* (limiting factors) and *how* (method + version), so
  downstream stages (04 crop planning) can trust and audit them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


# ------------------------------------------------------------------ enums
class SuitabilityClass(str, Enum):
    S1 = "S1"  # highly suitable
    S2 = "S2"  # moderately suitable
    S3 = "S3"  # marginally suitable
    N = "N"    # not suitable

    @property
    def rank(self) -> int:
        return {"S1": 3, "S2": 2, "S3": 1, "N": 0}[self.value]

    @classmethod
    def worst(cls, classes: list["SuitabilityClass"]) -> "SuitabilityClass":
        if not classes:
            raise ValueError("Cannot take the worst of an empty list of classes")
        return min(classes, key=lambda c: c.rank)


class Season(str, Enum):
    MEHER = "meher"          # main rains, roughly June to September
    BELG = "belg"            # short rains, roughly February to May
    DRY_IRRIGATED = "dry"    # irrigated dry season


class Direction(str, Enum):
    """How a factor relates to suitability."""
    RANGE = "range"            # an optimum band, worse on both sides (temperature, pH, altitude)
    LOWER_IS_BETTER = "lower"  # slope, erosion risk
    HIGHER_IS_BETTER = "higher"  # soil depth, organic carbon


class Method(str, Enum):
    FAO_LIMITING = "fao_limiting_factor"   # class = worst factor class
    AHP_WLC = "ahp_weighted_linear"        # weighted linear combination of fuzzy scores
    DEEP_LEARNING = "deep_learning"        # learned model (PyTorch)


# ------------------------------------------------------------------ value objects
@dataclass(frozen=True)
class LandFactor:
    code: str          # e.g. "slope_pct"
    name: str          # e.g. "Slope"
    unit: str          # e.g. "%"
    direction: Direction


@dataclass(frozen=True)
class FactorObservation:
    factor: LandFactor
    value: float
    source: str                    # e.g. "Copernicus DEM GLO-30"
    std: float | None = None       # measurement / model uncertainty, same unit as value
    observed_on: date | None = None


@dataclass(frozen=True)
class ClassBreaks:
    """
    Class thresholds for one factor.

    For RANGE factors, give the S1 optimum band and the wider S2 and S3 bands:
        s3_low <= s2_low <= s1_low <= s1_high <= s2_high <= s3_high
    Outside [s3_low, s3_high] the land is N.

    For LOWER_IS_BETTER only the *_high values are used; for HIGHER_IS_BETTER only *_low.
    """
    s1_low: float = float("-inf")
    s1_high: float = float("inf")
    s2_low: float = float("-inf")
    s2_high: float = float("inf")
    s3_low: float = float("-inf")
    s3_high: float = float("inf")

    def __post_init__(self) -> None:
        lows = [self.s3_low, self.s2_low, self.s1_low]
        highs = [self.s1_high, self.s2_high, self.s3_high]
        if lows != sorted(lows) or highs != sorted(highs) or self.s1_low > self.s1_high:
            raise ValueError(f"Class breaks are not nested S1 within S2 within S3: {self}")


@dataclass(frozen=True)
class CropRequirement:
    crop: str
    factor: LandFactor
    breaks: ClassBreaks
    weight: float = 1.0          # relative importance (AHP); normalised later
    note: str = ""               # provenance, e.g. "indicative, to calibrate with ARARI trials"


@dataclass(frozen=True)
class CropProfile:
    crop: str
    season: Season
    requirements: tuple[CropRequirement, ...]

    def requirement(self, factor_code: str) -> CropRequirement:
        for r in self.requirements:
            if r.factor.code == factor_code:
                return r
        raise KeyError(f"{self.crop} has no requirement for factor '{factor_code}'")


# ------------------------------------------------------------------ entities
@dataclass
class Plot:
    plot_id: str
    holder_id: str                 # pseudonymous household ID, never a personal name on the public site
    area_ha: float
    kebele: str
    woreda: str
    geometry_wkt: str | None = None
    certificate_level: int | None = None   # 1st or 2nd level land-use certification
    observations: dict[str, FactorObservation] = field(default_factory=dict)

    def observe(self, obs: FactorObservation) -> None:
        self.observations[obs.factor.code] = obs


@dataclass
class PlanningCluster:
    cluster_id: str
    name: str
    plots: list[Plot] = field(default_factory=list)

    @property
    def area_ha(self) -> float:
        return sum(p.area_ha for p in self.plots)


@dataclass(frozen=True)
class FactorResult:
    factor_code: str
    value: float
    klass: SuitabilityClass
    score: float                   # fuzzy membership in [0, 1]


@dataclass(frozen=True)
class SuitabilityAssessment:
    target_id: str                 # plot_id, cluster_id or raster cell id
    crop: str
    season: Season
    klass: SuitabilityClass
    score: float                   # 0..1 aggregated suitability
    limiting_factors: tuple[str, ...]
    factor_results: tuple[FactorResult, ...]
    method: Method
    method_version: str
    uncertainty: float | None = None   # e.g. std of score under input uncertainty

    def summary(self) -> str:
        lim = ", ".join(self.limiting_factors) or "none"
        unc = f" ±{self.uncertainty:.2f}" if self.uncertainty is not None else ""
        return (f"{self.target_id} | {self.crop} ({self.season.value}): {self.klass.value} "
                f"score {self.score:.2f}{unc} | limiting: {lim} | {self.method.value} v{self.method_version}")

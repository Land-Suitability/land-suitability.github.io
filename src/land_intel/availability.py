"""
Land availability: which land may be farmed at all, and on what terms.

Suitability answers "how well would teff grow here?". Availability answers an earlier question:
"is this land open to farming, and what would it take?". A highly suitable cell under a church
forest, a lake, a town or a protected slope is not available, however good its soil.

Analogy: suitability is a job applicant's skills; availability is whether the applicant is free to
take the job. Planning needs both, and availability is checked first.

Ubiquitous language
-------------------
LandCover          What covers the ground today (ESA WorldCover-like classes).
Constraint         A rule that removes land (HARD) or makes it conditional (SOFT), with its reason.
AvailabilityStatus IN_USE      current cropland: available to the plan now
                   EXPANDABLE  open land (grassland, shrubland) on gentle slopes, no other claim
                   CONDITIONAL possible only with investment or agreement (terraces, communal grazing, remote)
                   EXCLUDED    never planned: forest, water, wetland, built-up, protected, very steep, buffers
AvailabilityResult The status of every cell with a bit mask of the reasons, so every decision is explainable.
AvailableLand      Hectares by status, and the hectares that are both available and suitable (per crop),
                   which is what stage 04 plans with.

Design notes
------------
* Hard constraints always win over soft ones; reasons are kept as bit flags so a map can show
  "excluded because forest AND steep", not just "excluded".
* Thresholds are indicative and live in AvailabilityRules, to be agreed with the woreda office.
* Land is held under use rights: "expandable" means a candidate for discussion with the kebele,
  never land to be taken.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag

import numpy as np


class LandCover(IntEnum):
    """Land cover classes, aligned with ESA WorldCover codes where one exists."""
    FOREST = 10
    SHRUBLAND = 20
    GRASSLAND = 30
    CROPLAND = 40
    BUILT_UP = 50
    BARE = 60
    WATER = 80
    WETLAND = 90


class AvailabilityStatus(IntEnum):
    EXCLUDED = 0
    CONDITIONAL = 1
    EXPANDABLE = 2
    IN_USE = 3


class Reason(IntFlag):
    """Why a cell is excluded (hard) or conditional (soft). Combined as bit flags."""
    NONE = 0
    # hard
    FOREST = 1 << 0
    WATER = 1 << 1
    WETLAND = 1 << 2
    BUILT_UP = 1 << 3
    PROTECTED = 1 << 4          # e.g. church forest, reserve, sacred site
    VERY_STEEP = 1 << 5
    WATER_BUFFER = 1 << 6       # riparian strip kept for erosion control and environmental flow
    BARE = 1 << 7
    # soft
    TERRACES_NEEDED = 1 << 8    # moderate slope: farmable with soil and water conservation works
    COMMUNAL_GRAZING = 1 << 9   # needs a community agreement before any change of use
    REMOTE = 1 << 10            # far from a road: inputs and harvest are hard to move

    @classmethod
    def hard(cls) -> "Reason":
        return cls.FOREST | cls.WATER | cls.WETLAND | cls.BUILT_UP | cls.PROTECTED | cls.VERY_STEEP | cls.WATER_BUFFER | cls.BARE

    @classmethod
    def soft(cls) -> "Reason":
        return cls.TERRACES_NEEDED | cls.COMMUNAL_GRAZING | cls.REMOTE


REASON_TEXT = {
    Reason.FOREST: "forest", Reason.WATER: "open water", Reason.WETLAND: "wetland", Reason.BUILT_UP: "built-up",
    Reason.PROTECTED: "protected area", Reason.VERY_STEEP: "very steep slope", Reason.WATER_BUFFER: "river or lake buffer",
    Reason.BARE: "bare rock or soil", Reason.TERRACES_NEEDED: "terraces needed", Reason.COMMUNAL_GRAZING: "communal grazing",
    Reason.REMOTE: "far from a road",
}


@dataclass(frozen=True)
class AvailabilityRules:
    """Indicative thresholds (to be agreed with the woreda office and kebele land committees)."""
    max_slope_pct: float = 30.0         # above this: excluded (Ethiopian practice limits cultivation of steep land)
    terrace_slope_pct: float = 15.0     # between this and max: conditional, terraces or bunds needed
    water_buffer_m: float = 30.0        # strip along rivers and lakes kept out of cultivation
    remote_road_km: float = 5.0         # farther than this from a road: conditional
    cell_size_m: float = 250.0

    def __post_init__(self):
        if not 0 < self.terrace_slope_pct < self.max_slope_pct:
            raise ValueError(f"need 0 < terrace slope ({self.terrace_slope_pct}) < max slope ({self.max_slope_pct})")
        if self.cell_size_m <= 0:
            raise ValueError("cell size must be positive")

    @property
    def cell_ha(self) -> float:
        return self.cell_size_m ** 2 / 10_000


@dataclass
class AvailabilityResult:
    status: np.ndarray            # AvailabilityStatus values, int8
    reasons: np.ndarray           # Reason bit masks, int32
    rules: AvailabilityRules

    def hectares(self) -> dict[str, float]:
        return {s.name: float((self.status == s).sum() * self.rules.cell_ha) for s in AvailabilityStatus}

    def reason_hectares(self) -> dict[str, float]:
        """Area carrying each reason (a cell can carry several, so these do not add up to the total)."""
        return {REASON_TEXT[r]: float(((self.reasons & int(r)) != 0).sum() * self.rules.cell_ha)
                for r in Reason if r and r in REASON_TEXT}

    def explain(self, i: int, j: int) -> str:
        st = AvailabilityStatus(int(self.status[i, j]))
        why = [REASON_TEXT[r] for r in Reason if r and r in REASON_TEXT and int(self.reasons[i, j]) & int(r)]
        return f"{st.name.lower()}" + (f" ({', '.join(why)})" if why else "")


# ------------------------------------------------------------------ engine
def _buffer(mask: np.ndarray, cells: int) -> np.ndarray:
    """Grow a boolean mask by `cells` in the 8 directions (a cheap raster buffer, no SciPy needed)."""
    out = mask.copy()
    for _ in range(cells):
        g = out.copy()
        g[1:, :] |= out[:-1, :]; g[:-1, :] |= out[1:, :]; g[:, 1:] |= out[:, :-1]; g[:, :-1] |= out[:, 1:]
        g[1:, 1:] |= out[:-1, :-1]; g[:-1, :-1] |= out[1:, 1:]; g[1:, :-1] |= out[:-1, 1:]; g[:-1, 1:] |= out[1:, :-1]
        out = g
    return out


def assess_availability(cover: np.ndarray, slope_pct: np.ndarray, protected: np.ndarray, grazing: np.ndarray,
                        road_km: np.ndarray, rules: AvailabilityRules = AvailabilityRules()) -> AvailabilityResult:
    """
    Classify every cell as IN_USE, EXPANDABLE, CONDITIONAL or EXCLUDED, with the reasons.

    cover      LandCover codes (int)            protected  True where a protected area or church forest lies
    slope_pct  slope in percent                 grazing    True where land is communal grazing
    road_km    distance to the nearest road (km)
    """
    arrays = {"cover": cover, "slope_pct": slope_pct, "protected": protected, "grazing": grazing, "road_km": road_km}
    shapes = {k: np.shape(v) for k, v in arrays.items()}
    if len(set(shapes.values())) != 1:
        raise ValueError(f"layers are not co-registered, shapes differ: {shapes}")
    unknown = set(np.unique(cover).tolist()) - {int(c) for c in LandCover}
    if unknown:
        raise ValueError(f"unknown land cover codes {sorted(unknown)}; expected {[int(c) for c in LandCover]}")
    if np.isnan(slope_pct).any() or np.isnan(road_km).any():
        raise ValueError("slope or road distance has missing values; fill or mask them before assessing availability")

    cover = np.asarray(cover)
    reasons = np.zeros(cover.shape, dtype=np.int32)

    def flag(mask, r: Reason):
        reasons[np.asarray(mask, dtype=bool)] |= int(r)

    # hard constraints
    flag(cover == LandCover.FOREST, Reason.FOREST)
    flag(cover == LandCover.WATER, Reason.WATER)
    flag(cover == LandCover.WETLAND, Reason.WETLAND)
    flag(cover == LandCover.BUILT_UP, Reason.BUILT_UP)
    flag(cover == LandCover.BARE, Reason.BARE)
    flag(protected, Reason.PROTECTED)
    flag(slope_pct > rules.max_slope_pct, Reason.VERY_STEEP)
    buffer_cells = int(np.ceil(rules.water_buffer_m / rules.cell_size_m))
    water = (cover == LandCover.WATER) | (cover == LandCover.WETLAND)
    flag(_buffer(water, buffer_cells) & ~water, Reason.WATER_BUFFER)
    # soft constraints
    flag((slope_pct > rules.terrace_slope_pct) & (slope_pct <= rules.max_slope_pct), Reason.TERRACES_NEEDED)
    flag(np.asarray(grazing, dtype=bool) & (cover != LandCover.CROPLAND), Reason.COMMUNAL_GRAZING)
    flag(road_km > rules.remote_road_km, Reason.REMOTE)

    hard = (reasons & int(Reason.hard())) != 0
    soft = (reasons & int(Reason.soft())) != 0
    open_land = (cover == LandCover.GRASSLAND) | (cover == LandCover.SHRUBLAND)

    status = np.full(cover.shape, AvailabilityStatus.EXCLUDED, dtype=np.int8)
    status[~hard & (cover == LandCover.CROPLAND)] = AvailabilityStatus.IN_USE           # soft reasons are kept as notes
    status[~hard & open_land & ~soft] = AvailabilityStatus.EXPANDABLE
    status[~hard & open_land & soft] = AvailabilityStatus.CONDITIONAL
    return AvailabilityResult(status=status, reasons=reasons, rules=rules)


def available_and_suitable(avail: AvailabilityResult, suitability_rank: np.ndarray,
                           statuses=(AvailabilityStatus.IN_USE, AvailabilityStatus.EXPANDABLE)) -> dict[str, float]:
    """
    Hectares that are both available (in the given statuses) and in each suitability class.
    suitability_rank: 3 = S1 .. 0 = N, -1 = missing (from scoring.assess_grid).
    """
    if suitability_rank.shape != avail.status.shape:
        raise ValueError(f"suitability {suitability_rank.shape} and availability {avail.status.shape} grids differ")
    ok = np.isin(avail.status, [int(s) for s in statuses])
    return {lab: float((ok & (suitability_rank == v)).sum() * avail.rules.cell_ha)
            for lab, v in [("S1", 3), ("S2", 2), ("S3", 1), ("N", 0)]}


@dataclass
class AvailableLand:
    """What stage 04 receives per planning cluster: how much land is open, and how good it is per crop."""
    cluster_id: str
    hectares_by_status: dict[str, float]
    suitable_available_ha: dict[str, dict[str, float]] = field(default_factory=dict)   # crop -> class -> ha
    rules_version: str = "0.1"

    def plannable_ha(self, crop: str, classes=("S1", "S2")) -> float:
        if crop not in self.suitable_available_ha:
            raise KeyError(f"no suitability for {crop!r}; known: {sorted(self.suitable_available_ha)}")
        return sum(self.suitable_available_ha[crop].get(c, 0.0) for c in classes)

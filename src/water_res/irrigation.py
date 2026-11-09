"""
Irrigated land suitability (Phase 1, module 3): which available land can be irrigated well, by which method.

Module 1 says which land is available; module 2 says how each field can reach water and how much each
source gives per month. This module joins them, following the FAO approach to land evaluation for
irrigated agriculture: every irrigation method has its own land requirements, the worst factor sets
the class, and then the water of each source limits how much of its command area can be irrigated.

Analogy: good land and water are like a cook and ingredients; irrigation is the kitchen that brings
them together. The kitchen has to fit the room: furrows need flat land, drip fits almost anywhere.

Ubiquitous language
-------------------
IrrigationMethod     SURFACE (furrow, basin), SPRINKLER, DRIP, each with an application efficiency.
FactorBand           S1/S2/S3 limits for one land factor and one method (beyond S3: N).
IrrigationClass      S1..N per field and method = the worst of its land factors and its water access.
CommandArea          The fields one source serves: hectares per class and method, and the hectares
                     its water can actually irrigate in the dry season with each method.
ReferenceDemand      Crop-neutral water need: Kc 1.0 over the dry season (Nov to Apr), net of
                     effective rain; the crop comes in module 4.

Design notes
------------
* Thresholds are indicative (FAO land evaluation practice), to be calibrated with the regional
  irrigation office; soil texture, infiltration and salinity are not yet in the hand-off and are
  flagged as missing factors, never assumed suitable.
* Per field, the best method is the cheapest one that reaches the field's best class (surface, then
  sprinkler, then drip). Drip's water saving is weighed per command area, where water is the limit.
* A command area is everything one water body serves: all intakes of a stream basin share its water.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np

from .hydrology import effective_rainfall

DRY_SEASON = (10, 11, 0, 1, 2, 3)          # Nov, Dec, Jan, Feb, Mar, Apr (month index)
DAYS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
CLS = {3: "S1", 2: "S2", 1: "S3", 0: "N", -1: "not assessed"}


class IrrigationMethod(str, Enum):
    SURFACE = "surface"
    SPRINKLER = "sprinkler"
    DRIP = "drip"

    @property
    def efficiency(self) -> float:          # same mid values as the stage 02 budget
        return {"surface": 0.60, "sprinkler": 0.75, "drip": 0.90}[self.value]


@dataclass(frozen=True)
class FactorBand:
    s1: float
    s2: float
    s3: float
    higher_is_better: bool

    def __post_init__(self):
        ok = (self.s1 >= self.s2 >= self.s3) if self.higher_is_better else (self.s1 <= self.s2 <= self.s3)
        if not ok:
            raise ValueError(f"bands must be nested S1 -> S3, got {self}")

    def rank(self, v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=float)
        if self.higher_is_better:
            return np.select([v >= self.s1, v >= self.s2, v >= self.s3], [3, 2, 1], 0)
        return np.select([v <= self.s1, v <= self.s2, v <= self.s3], [3, 2, 1], 0)


# indicative requirements per method (FAO irrigation land evaluation practice, highland conditions)
REQUIREMENTS = {
    IrrigationMethod.SURFACE: {"slope_pct": FactorBand(2, 5, 8, False), "soil_depth_cm": FactorBand(90, 60, 40, True),
                               "drainage_class": FactorBand(4, 3, 2, True)},
    IrrigationMethod.SPRINKLER: {"slope_pct": FactorBand(5, 12, 20, False), "soil_depth_cm": FactorBand(75, 50, 30, True),
                                 "drainage_class": FactorBand(3.5, 2.5, 1.5, True)},
    IrrigationMethod.DRIP: {"slope_pct": FactorBand(8, 15, 25, False), "soil_depth_cm": FactorBand(60, 40, 25, True),
                            "drainage_class": FactorBand(3, 2, 1.5, True)},
}
# water access class (module 2 names) -> rank per method
ACCESS_RANK = {
    IrrigationMethod.SURFACE: {"GRAVITY": 3, "PUMPED": 2, "GROUNDWATER": 1, "HARVEST_ONLY": 0},
    IrrigationMethod.SPRINKLER: {"GRAVITY": 2, "PUMPED": 3, "GROUNDWATER": 2, "HARVEST_ONLY": 0},
    IrrigationMethod.DRIP: {"GRAVITY": 3, "PUMPED": 3, "GROUNDWATER": 3, "HARVEST_ONLY": 1},
}
MISSING_FACTORS = ("soil texture and infiltration", "salinity and sodicity")


# ------------------------------------------------------------------ hand-off from module 2
@dataclass(frozen=True)
class WaterAccessGrid:
    access: np.ndarray            # module 2 AccessClass codes
    source: np.ndarray            # index into sources, -1 for none
    lift_m: np.ndarray
    sources: list[dict]
    access_codes: dict[str, int]
    et0_mm_day: np.ndarray        # 12 months
    rain_mm: np.ndarray           # 12 months
    provenance: dict

    def access_name(self) -> np.ndarray:
        inv = {v: k for k, v in self.access_codes.items()}
        return np.vectorize(lambda c: inv[int(c)])(self.access)


def load_water_handoff(path: Path) -> WaterAccessGrid:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"module 2 hand-off not found at {path}; run src/demo_water_map.py") from None
    if d.get("contract") != "aiae.phase1.water_availability" or d.get("version") != "0.1":
        raise ValueError(f"unexpected hand-off {d.get('contract')!r} v{d.get('version')!r}")
    rows, cols = d["grid"]["rows"], d["grid"]["cols"]
    access = np.asarray(d["layers"]["access"], dtype=int)
    source = np.asarray(d["layers"]["source"], dtype=int)
    lift = np.asarray([[np.nan if v is None else v for v in r] for r in d["layers"]["lift_m"]], dtype=float)
    for name, a in (("access", access), ("source", source), ("lift_m", lift)):
        if a.shape != (rows, cols):
            raise ValueError(f"layer {name} has shape {a.shape}, expected {(rows, cols)}")
    if source.max() >= len(d["sources"]):
        raise ValueError("a field points to a source that is not in the source list")
    clim = d["climate"]
    if len(clim["et0_mm_day"]) != 12 or len(clim["rain_mm"]) != 12:
        raise ValueError("climate needs 12 monthly values")
    return WaterAccessGrid(access, source, lift, d["sources"], d["codes"]["access"],
                           np.asarray(clim["et0_mm_day"], float), np.asarray(clim["rain_mm"], float),
                           {"module_2": d.get("producer"), "module_1": d.get("from_module_1")})


# ------------------------------------------------------------------ assessment
@dataclass
class IrrigationSuitability:
    rank: dict[IrrigationMethod, np.ndarray]          # 3..0, -1 not assessed
    limiting: dict[IrrigationMethod, np.ndarray]      # factor name per cell ("" if none)
    best_method: np.ndarray                           # method value per cell ("" if none S1-S3)
    best_rank: np.ndarray
    cell_ha: float

    def hectares(self, method: IrrigationMethod) -> dict[str, float]:
        r = self.rank[method]
        return {CLS[v]: float((r == v).sum() * self.cell_ha) for v in (3, 2, 1, 0)}


def assess_irrigation(land_layers: dict[str, np.ndarray], available: np.ndarray, access_names: np.ndarray,
                      cell_ha: float) -> IrrigationSuitability:
    """Class per field and method: the worst of slope, soil depth, drainage and water access."""
    shapes = {k: land_layers[k].shape for k in ("slope_pct", "soil_depth_cm", "drainage_class")}
    shapes["available"], shapes["access"] = available.shape, access_names.shape
    if len(set(shapes.values())) != 1:
        raise ValueError(f"grids differ in shape: {shapes}")
    rank, limiting = {}, {}
    for m, req in REQUIREMENTS.items():
        parts = {f: band.rank(land_layers[f]) for f, band in req.items()}
        parts["water access"] = np.vectorize(lambda a: ACCESS_RANK[m].get(a, 0))(access_names)
        stack = np.stack(list(parts.values()))
        r = stack.min(axis=0)
        names = np.array(list(parts.keys()))
        lim = np.where(r < 3, names[np.argmin(stack, axis=0)], "")
        rank[m] = np.where(available, r, -1)
        limiting[m] = np.where(available, lim, "")
    order = [IrrigationMethod.SURFACE, IrrigationMethod.SPRINKLER, IrrigationMethod.DRIP]   # tie: the cheapest first
    stack = np.stack([rank[m] for m in order])
    best_i = np.argmax(stack, axis=0)
    best_rank = stack.max(axis=0)
    best = np.where(best_rank >= 1, np.array([m.value for m in order])[best_i], "")
    return IrrigationSuitability(rank, limiting, best, best_rank, cell_ha)


def reference_gross_m3_per_ha(et0_mm_day: np.ndarray, rain_mm: np.ndarray, method: IrrigationMethod) -> np.ndarray:
    """Dry-season reference demand (Kc 1.0) per month, gross for the method; zero outside Nov to Apr."""
    net_mm = np.maximum(et0_mm_day * DAYS - effective_rainfall(rain_mm), 0)
    out = np.zeros(12)
    idx = list(DRY_SEASON)
    out[idx] = net_mm[idx] / method.efficiency * 10
    return out


@dataclass
class CommandArea:
    source_id: str
    kind: str
    hectares: dict[str, dict[str, float]] = field(default_factory=dict)   # method -> class -> ha
    best_method_ha: dict[str, float] = field(default_factory=dict)        # method -> ha of S1/S2 where it is best
    water_limited_ha: dict[str, float] = field(default_factory=dict)      # method -> ha the water can irrigate
    sustainable_m3: tuple[float, ...] = ()
    mean_altitude_m: float = 0.0

    def suitable_ha(self, method: str) -> float:
        h = self.hectares.get(method, {})
        return h.get("S1", 0.0) + h.get("S2", 0.0)

    def irrigable_ha(self, method: str) -> float:
        """Land and water together: the smaller of suitable land and what the water can serve."""
        return min(self.suitable_ha(method), self.water_limited_ha.get(method, 0.0))


def command_areas(suit: IrrigationSuitability, water: WaterAccessGrid, altitude: np.ndarray) -> list[CommandArea]:
    """
    One command area per water body: every field served by any intake of a stream basin (or by one
    spring or well site). A basin's intakes share one supply, capped month by month by the outlet flow
    (the largest flow along the network); water-limited hectares use the leanest dry-season month.
    """
    out = []
    demand = {m: reference_gross_m3_per_ha(water.et0_mm_day, water.rain_mm, m) for m in IrrigationMethod}
    bodies: dict[str, list[int]] = {}
    for k, src in enumerate(water.sources):
        bodies.setdefault(src.get("water_body") or src["id"], []).append(k)
    for body, members in bodies.items():
        cells = np.isin(water.source, members)
        if not cells.any():
            continue
        kind = water.sources[members[0]]["kind"]
        flows = np.array([water.sources[k]["sustainable_m3"] for k in members], float)
        supply = flows.max(axis=0) if kind == "stream" else flows.sum(axis=0)
        ca = CommandArea(body, kind, sustainable_m3=tuple(float(v) for v in supply), mean_altitude_m=float(altitude[cells].mean()))
        for m in IrrigationMethod:
            r = suit.rank[m][cells]
            ca.hectares[m.value] = {CLS[v]: float((r == v).sum() * suit.cell_ha) for v in (3, 2, 1, 0)}
            ca.best_method_ha[m.value] = float(((suit.best_method[cells] == m.value) & (suit.best_rank[cells] >= 2)).sum() * suit.cell_ha)
            dm = demand[m]
            if src["kind"] == "groundwater":          # storage: a year's water against the season's need
                ca.water_limited_ha[m.value] = float(supply.sum() / dm.sum())
            else:                                      # no storage: the tightest dry-season month decides
                ca.water_limited_ha[m.value] = float(min(supply[i] / dm[i] for i in DRY_SEASON if dm[i] > 0))
        out.append(ca)
    return out

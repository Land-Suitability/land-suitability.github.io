"""
Water availability mapping (Phase 1, module 2): where water can come from, and how much each month.

Stage 02's water budget answers "is there enough water for this cluster?". This module answers the
spatial questions that come before it: where are the sources, how much can each give in each month
without harming the river or the aquifer, and which available field can reach which source.

Analogy: the budget is the size of the household's water tank; this map shows the taps and wells,
and how far each house is from them.

Ubiquitous language
-------------------
Terrain             The elevation grid, filled so that every cell drains somewhere.
StreamNetwork       Cells where enough upstream area collects to form a stream (D8 routing).
StreamFlow          Monthly flow of each stream cell = upstream area x specific runoff; the
                    sustainable share keeps an environmental flow in the river.
GroundwaterPotential  A 0..1 index from weighted factors (geology, fractures, slope, rainfall,
                    stream density, soil drainage), in five classes from very low to very high.
WaterPoint          A mapped source: stream reach, spring or shallow groundwater, with its
                    sustainable monthly yield and how well that yield is known.
AccessClass         How an available field can get water:
                      GRAVITY      a canal from a higher stream or spring, within reach
                      PUMPED       a short pumped lift from a stream or spring
                      GROUNDWATER  shallow wells on site (high groundwater potential)
                      HARVEST_ONLY only rainwater harvesting (ponds, tanks)
WaterAvailabilityMap  The output: access class, serving source, distance and lift per field, and
                    each source's sustainable water per dependent hectare in its leanest month.

Design notes
------------
* Every threshold lives in MappingRules and is indicative, to be checked with the woreda water office.
* Satellite and terrain analysis give POTENTIAL; yields stay "indicative" until gauged or pump-tested.
* Only land that module 1 marked available is assessed; nothing here makes excluded land usable.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import IntEnum

import numpy as np

from .domain import Confidence, MONTHS

# D8 neighbour offsets (row, col) and their distance in cells
_NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
_ND = [np.sqrt(2), 1, np.sqrt(2), 1, 1, np.sqrt(2), 1, np.sqrt(2)]


class AccessClass(IntEnum):
    NOT_ASSESSED = 0     # land not available (module 1)
    HARVEST_ONLY = 1
    GROUNDWATER = 2
    PUMPED = 3
    GRAVITY = 4


class GwClass(IntEnum):
    VERY_LOW = 1
    LOW = 2
    MODERATE = 3
    HIGH = 4
    VERY_HIGH = 5


class Geology(IntEnum):
    MASSIVE_BASALT = 1      # trap basalt of the escarpments: little storage
    FRACTURED_BASALT = 2    # weathered, fractured plateau basalt: moderate
    ALLUVIUM = 3            # valley and lake-shore sediments: high


@dataclass(frozen=True)
class MappingRules:
    """Indicative thresholds and coefficients (agree locally before use)."""
    stream_min_km2: float = 2.0                  # upstream area that forms a stream
    environmental_flow_fraction: float = 0.30    # same rule as the stage 02 budget
    min_dry_flow_ls: float = 5.0                 # a stream reach must give this in the leanest month to count
    gravity_max_km: float = 3.0                  # longest gravity canal considered
    canal_slope: float = 0.002                   # head lost per metre of canal (m/m)
    freeboard_m: float = 2.0
    pump_max_km: float = 1.5
    pump_max_lift_m: float = 30.0
    recharge_share: float = 0.40                 # share of recharge that may be pumped (stage 02 rule)
    recharge_coef: dict = field(default_factory=lambda: {Geology.MASSIVE_BASALT: 0.04, Geology.FRACTURED_BASALT: 0.10, Geology.ALLUVIUM: 0.16})
    gw_weights: dict = field(default_factory=lambda: {"geology": 0.30, "lineaments": 0.20, "slope": 0.15,
                                                      "rainfall": 0.15, "stream_density": 0.10, "soil_drainage": 0.10})
    gw_breaks: tuple = (0.38, 0.48, 0.58, 0.68)  # very low | low | moderate | high | very high

    def __post_init__(self):
        if abs(sum(self.gw_weights.values()) - 1.0) > 1e-6:
            raise ValueError(f"groundwater weights must sum to 1, got {sum(self.gw_weights.values()):.3f}")
        if list(self.gw_breaks) != sorted(self.gw_breaks):
            raise ValueError("groundwater class breaks must increase")
        if not 0 <= self.environmental_flow_fraction < 1:
            raise ValueError("environmental flow fraction must be in [0, 1)")


@dataclass(frozen=True)
class WaterPoint:
    point_id: str
    kind: str                       # "stream" | "spring" | "groundwater"
    cell: tuple[int, int]
    elevation_m: float
    sustainable_m3: tuple[float, ...]   # 12 months, January first
    confidence: Confidence = Confidence.INDICATIVE

    @property
    def leanest_month(self) -> int:
        return int(np.argmin(self.sustainable_m3))


@dataclass
class WaterAvailabilityMap:
    access: np.ndarray              # AccessClass per cell
    source_id: np.ndarray           # serving point id per cell ("" if none)
    distance_km: np.ndarray
    lift_m: np.ndarray              # field minus source elevation (negative = source higher)
    points: dict[str, WaterPoint]
    cell_ha: float

    def hectares(self) -> dict[str, float]:
        return {c.name: float((self.access == c).sum() * self.cell_ha) for c in AccessClass}

    def dependent_ha(self) -> dict[str, float]:
        ids, counts = np.unique(self.source_id[self.source_id != ""], return_counts=True)
        return {str(i): float(n * self.cell_ha) for i, n in zip(ids, counts)}

    def leanest_month_m3_per_ha(self) -> dict[str, tuple[str, float]]:
        """Each surface source's sustainable water per dependent hectare in its leanest month."""
        out = {}
        for pid, ha in self.dependent_ha().items():
            p = self.points[pid]
            if p.kind == "groundwater" or ha <= 0:
                continue
            m = p.leanest_month
            out[pid] = (MONTHS[m], p.sustainable_m3[m] / ha)
        return out


# ------------------------------------------------------------------ terrain hydrology
def fill_depressions(z: np.ndarray, eps: float = 1e-3) -> np.ndarray:
    """Priority-flood fill (Barnes et al. 2014): raise pits so every cell drains to the edge or a lake."""
    z = np.asarray(z, dtype=float)
    if np.isnan(z).any():
        raise ValueError("elevation has missing values")
    n, m = z.shape
    out = z.copy()
    done = np.zeros_like(z, dtype=bool)
    heap = []
    for i in range(n):
        for j in range(m):
            if i in (0, n - 1) or j in (0, m - 1):
                heapq.heappush(heap, (out[i, j], i, j)); done[i, j] = True
    while heap:
        h, i, j = heapq.heappop(heap)
        for di, dj in _NB:
            a, b = i + di, j + dj
            if 0 <= a < n and 0 <= b < m and not done[a, b]:
                done[a, b] = True
                out[a, b] = max(out[a, b], h + eps)
                heapq.heappush(heap, (out[a, b], a, b))
    return out


def d8_receivers(filled: np.ndarray) -> np.ndarray:
    """For every cell, the flat index of the steepest downhill neighbour (-1 at outlets on the edge)."""
    n, m = filled.shape
    rec = np.full(n * m, -1, dtype=int)
    for i in range(n):
        for j in range(m):
            best, target = 0.0, -1
            for (di, dj), d in zip(_NB, _ND):
                a, b = i + di, j + dj
                if 0 <= a < n and 0 <= b < m:
                    drop = (filled[i, j] - filled[a, b]) / d
                    if drop > best:
                        best, target = drop, a * m + b
            rec[i * m + j] = target
    return rec


def flow_accumulation(filled: np.ndarray, receivers: np.ndarray) -> np.ndarray:
    """Number of cells draining through each cell, itself included (process from high to low)."""
    acc = np.ones(filled.size)
    for k in np.argsort(filled.ravel())[::-1]:
        r = receivers[k]
        if r >= 0:
            acc[r] += acc[k]
    return acc.reshape(filled.shape)


def stream_flow_m3(upstream_km2: np.ndarray, specific_runoff_mm: tuple[float, ...]) -> np.ndarray:
    """Monthly flow (m3) at every cell: area (km2) x runoff depth (mm) x 1000. Shape (12, rows, cols)."""
    if len(specific_runoff_mm) != 12:
        raise ValueError("specific runoff needs 12 monthly values")
    q = np.asarray(specific_runoff_mm, dtype=float)[:, None, None]
    return upstream_km2[None] * q * 1000.0


# ------------------------------------------------------------------ groundwater potential
def groundwater_potential(factors: dict[str, np.ndarray], rules: MappingRules = MappingRules()) -> tuple[np.ndarray, np.ndarray]:
    """Weighted overlay of factor scores in 0..1. Returns (index, GwClass grid)."""
    missing = set(rules.gw_weights) - set(factors)
    if missing:
        raise KeyError(f"groundwater factors missing: {sorted(missing)}")
    shapes = {k: factors[k].shape for k in rules.gw_weights}
    if len(set(shapes.values())) != 1:
        raise ValueError(f"factor grids differ in shape: {shapes}")
    for k in rules.gw_weights:
        f = factors[k]
        if np.nanmin(f) < -1e-9 or np.nanmax(f) > 1 + 1e-9:
            raise ValueError(f"factor {k} must be scored in 0..1 before weighting")
    idx = sum(w * factors[k] for k, w in rules.gw_weights.items())
    cls = np.digitize(idx, rules.gw_breaks) + 1
    return idx, cls.astype(int)


# ------------------------------------------------------------------ access per field
def water_access(available: np.ndarray, elevation: np.ndarray, points: list[WaterPoint], gw_class: np.ndarray,
                 gw_m3_per_month: np.ndarray, cell_m: float, rules: MappingRules = MappingRules()) -> WaterAvailabilityMap:
    """
    For each available cell, the best way to get water, tried in order of cost:
      gravity canal from a higher stream or spring -> short pumped lift -> shallow wells on site -> harvest only.
    Among reachable gravity (or pumped) sources, the one with the most water in its leanest month
    wins, and distance breaks ties: a field should lean on a stream, not on a small spring next door.
    gw_m3_per_month: sustainable shallow-groundwater yield of each cell per month (recharge share applied).
    """
    if not (available.shape == elevation.shape == gw_class.shape == gw_m3_per_month.shape):
        raise ValueError("available, elevation and groundwater grids must share one shape")
    n, m = elevation.shape
    access = np.zeros((n, m), dtype=int)
    source = np.full((n, m), "", dtype=object)
    dist = np.full((n, m), np.nan)
    lift = np.full((n, m), np.nan)
    surf = [p for p in points if p.kind in ("stream", "spring")]
    if surf:
        pi = np.array([p.cell[0] for p in surf]); pj = np.array([p.cell[1] for p in surf])
        pz = np.array([p.elevation_m for p in surf])
        lean = np.array([min(p.sustainable_m3) for p in surf])
    by_id = {p.point_id: p for p in points}
    for i, j in zip(*np.nonzero(available)):
        z = elevation[i, j]
        if surf:
            d_km = np.hypot(pi - i, pj - j) * cell_m / 1000.0
            head_needed = z + d_km * 1000 * rules.canal_slope + rules.freeboard_m
            grav = (d_km <= rules.gravity_max_km) & (pz >= head_needed)
            pump = (d_km <= rules.pump_max_km) & (z - pz <= rules.pump_max_lift_m)
            for ok, cls in ((grav, AccessClass.GRAVITY), (pump, AccessClass.PUMPED)):
                if ok.any():
                    k = int(np.lexsort((np.where(ok, d_km, np.inf), np.where(ok, -lean, np.inf)))[0])
                    access[i, j], source[i, j], dist[i, j], lift[i, j] = cls, surf[k].point_id, d_km[k], z - pz[k]
                    break
        if access[i, j]:
            continue
        if gw_class[i, j] >= GwClass.HIGH:
            gid = f"GW-{i:02d}-{j:02d}"
            access[i, j], source[i, j], dist[i, j], lift[i, j] = AccessClass.GROUNDWATER, gid, 0.0, np.nan
        else:
            access[i, j] = AccessClass.HARVEST_ONLY
    # shallow-groundwater points exist only where a field uses one, with that cell's sustainable yield
    for i, j in zip(*np.nonzero(access == AccessClass.GROUNDWATER)):
        gid = source[i, j]
        by_id[gid] = WaterPoint(gid, "groundwater", (int(i), int(j)), float(elevation[i, j]), tuple([float(gw_m3_per_month[i, j])] * 12))
    return WaterAvailabilityMap(access, source, dist, lift, by_id, cell_m ** 2 / 10_000)

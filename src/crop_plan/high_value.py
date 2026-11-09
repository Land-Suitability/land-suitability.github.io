"""
High-value crop guidance (Phase 1, module 4): which high-value crops pay best on each irrigable
command area with its water, when to plant them, and how to grow them.

Module 3 hands over command areas: irrigable land per irrigation method and twelve months of water
per water body. This module turns them into stage 04 planning units and lets the existing planner
(a linear programme with monthly water limits) choose crops and planting dates, then writes a
production guide for every crop it recommends.

Analogy: modules 1 to 3 found the kitchen and the ingredients; this module writes the menu, and a
recipe card for each dish.

Ubiquitous language
-------------------
HighValueCrop     A crop profile: FAO-56 crop-coefficient curve, altitude range, yield, price, cost,
                  nursery time and a production calendar template. Values are INDICATIVE.
PlantingWindow    Transplanting dates the crop is offered at (mid-October to mid-January), so the
                  planner can stagger planting to fit the water month by month.
CommandAreaUnit   A module 3 command area as a stage 04 ClusterProfile: dry-season land (suitable
                  for its best method), monthly water, and a yield factor from altitude.
CropGuide         A recipe card: nursery, transplanting, irrigation per growth stage, fertilizer,
                  harvest and post-harvest steps with dates for one planting window.

Design notes
------------
* Water per month uses the same method as stage 02 (Kc x ET0 minus effective rain, divided by the
  method's efficiency); the climate comes with the module 3 hand-off, so no code crosses branches.
* Shallow wells draw on storage: a year's sustainable recharge is spread over the irrigation season
  (October to May) instead of being limited month by month.
* Prices, yields and costs are synthetic placeholders to be replaced by stage 05 market data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from .domain import ClusterProfile, CropOption, DemandSignal

DAYS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
IRRIGATION_SEASON = (9, 10, 11, 0, 1, 2, 3, 4)          # Oct..May (month index)
PLANTING_DATES = ((10, 15), (11, 15), (12, 15), (1, 15))  # (month, day): transplanting / sowing
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass(frozen=True)
class HighValueCrop:
    key: str
    name: str
    kc: tuple[float, float, float]           # FAO-56 Kc ini, mid, end
    stages: tuple[int, int, int, int]        # FAO-56 stage lengths (days) in the field
    altitude_opt: tuple[float, float]
    altitude_ok: tuple[float, float]
    yield_t_ha: float
    price_birr_t: float
    cost_birr_ha: float
    nursery_days: int                        # 0 = sown directly
    market_max_t: float                      # what regional and national buyers take from the pilot (synthetic)
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        lo, hi = self.altitude_ok
        if not (lo <= self.altitude_opt[0] <= self.altitude_opt[1] <= hi):
            raise ValueError(f"{self.key}: optimum altitude must sit inside the acceptable range")
        if min(self.yield_t_ha, self.price_birr_t) <= 0 or any(s <= 0 for s in self.stages):
            raise ValueError(f"{self.key}: yield, price and stage lengths must be positive")

    @property
    def field_days(self) -> int:
        return sum(self.stages)

    def altitude_factor(self, altitude_m: float) -> float:
        """Yield factor from altitude: 1.0 in the optimum band, 0.7 in the acceptable band, 0 outside."""
        if self.altitude_opt[0] <= altitude_m <= self.altitude_opt[1]:
            return 1.0
        if self.altitude_ok[0] <= altitude_m <= self.altitude_ok[1]:
            return 0.7
        return 0.0

    @property
    def margin_birr_ha(self) -> float:
        return self.yield_t_ha * self.price_birr_t - self.cost_birr_ha


# indicative profiles: Kc and stage lengths from FAO-56 tables 11 and 12; economics synthetic
CROPS = (
    HighValueCrop("onion", "Onion", (0.70, 1.05, 0.75), (15, 25, 70, 40), (1300, 2200), (900, 2600), 22, 18_000, 160_000, 45, 4_000,
                  ("Bulbs store for months in a dry, ventilated store (stage 10).",)),
    HighValueCrop("tomato", "Tomato", (0.60, 1.15, 0.80), (25, 35, 40, 25), (1000, 2000), (700, 2300), 25, 14_000, 190_000, 30, 2_500,
                  ("Perishable: harvest to a buyer within days; crates, not sacks.",)),
    HighValueCrop("pepper", "Hot pepper", (0.60, 1.05, 0.90), (25, 35, 40, 20), (1200, 2000), (900, 2300), 12, 30_000, 170_000, 40, 800,
                  ("Sells green or dried; dried red pepper keeps and travels well.",)),
    HighValueCrop("potato", "Potato", (0.50, 1.15, 0.75), (25, 30, 30, 30), (1800, 2800), (1500, 3200), 20, 12_000, 120_000, 0, 3_000,
                  ("Needs clean seed tubers; store in diffuse light, not in the dark.",)),
    HighValueCrop("garlic", "Garlic", (0.70, 1.00, 0.70), (20, 30, 70, 20), (1900, 2800), (1600, 3000), 9, 60_000, 230_000, 0, 400,
                  ("High value per kilogram; cured bulbs keep for months.",)),
)
EFFICIENCY = {"surface": 0.60, "sprinkler": 0.75, "drip": 0.90}


def effective_rainfall(p_mm) -> np.ndarray:
    """USDA-SCS monthly effective rainfall, the same formula as stage 02."""
    p = np.asarray(p_mm, dtype=float)
    return np.where(p <= 250, p * (125 - 0.2 * p) / 125, 125 + 0.1 * p)


def kc_curve(crop: HighValueCrop) -> np.ndarray:
    a, b, c, d = crop.stages
    k0, k1, k2 = crop.kc
    return np.concatenate([np.full(a, k0), np.linspace(k0, k1, b + 1)[1:], np.full(c, k1), np.linspace(k1, k2, d + 1)[1:]])


def water_need_m3_ha(crop: HighValueCrop, plant: tuple[int, int], et0_mm_day, rain_mm, method: str) -> np.ndarray:
    """Gross irrigation need per hectare and month for one planting date and method."""
    if method not in EFFICIENCY:
        raise ValueError(f"unknown irrigation method {method!r}; use {sorted(EFFICIENCY)}")
    et0, rain = np.asarray(et0_mm_day, float), np.asarray(rain_mm, float)
    if et0.shape != (12,) or rain.shape != (12,):
        raise ValueError("climate needs 12 monthly values")
    start = int(DAYS[: plant[0] - 1].sum()) + plant[1] - 1
    month_of_day = np.repeat(np.arange(12), DAYS)
    etc, days = np.zeros(12), np.zeros(12)
    for d, k in enumerate(kc_curve(crop)):
        m = month_of_day[(start + d) % 365]
        etc[m] += et0[m] * k
        days[m] += 1
    peff = effective_rainfall(rain) * days / DAYS
    return np.maximum(etc - peff, 0) / EFFICIENCY[method] * 10


def option_id(crop: HighValueCrop, plant: tuple[int, int], method: str) -> str:
    return f"{crop.key}_{MONTHS[plant[0] - 1].lower()}_{method}"


def crop_options(climate: dict, methods=("surface", "sprinkler", "drip")) -> tuple[list[CropOption], dict]:
    """Every crop x planting date x method as a stage 04 CropOption; returns (options, lookup)."""
    opts, meta = [], {}
    for crop in CROPS:
        for plant in PLANTING_DATES:
            for m in methods:
                w = water_need_m3_ha(crop, plant, climate["et0_mm_day"], climate["rain_mm"], m)
                oid = option_id(crop, plant, m)
                opts.append(CropOption(oid, crop.key, "dry", crop.field_days, crop.yield_t_ha, crop.price_birr_t,
                                       crop.cost_birr_ha, water_m3_ha=tuple(float(v) for v in w)))
                meta[oid] = (crop, plant, m)
    return opts, meta


def command_area_units(handoff: dict, meta: dict) -> list[ClusterProfile]:
    """Module 3 command areas as stage 04 planning units (dry season only)."""
    units = []
    for ca in handoff["command_areas"]:
        method = ca["best_method"]
        supply = np.asarray(ca["sustainable_m3"], float)
        if ca["kind"] == "groundwater":                     # storage: a year's water over the irrigation season
            spread = np.zeros(12)
            spread[list(IRRIGATION_SEASON)] = supply.sum() / len(IRRIGATION_SEASON)
            supply = spread
        suit = {oid: crop.altitude_factor(ca["mean_altitude_m"]) * 0.9      # 0.9: S1/S2 mix of the area
                for oid, (crop, _plant, m) in meta.items() if m == method}
        units.append(ClusterProfile(ca["source_id"], {"meher": 0.0, "dry": float(ca["suitable_ha"][method])},
                                    suit, {oid: 1.0 for oid in suit}, tuple(float(v) for v in supply)))
    return units


def market_demand() -> list[DemandSignal]:
    return [DemandSignal(c.key, 0.0, c.market_max_t) for c in CROPS]


def load_module3(path: Path) -> dict:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"module 3 hand-off not found at {path}; copy it from stage/02-water-resources "
                                "assets/handoff-irrigated-suitability.json") from None
    if d.get("contract") != "aiae.phase1.irrigated_suitability" or d.get("version") != "0.1":
        raise ValueError(f"unexpected hand-off {d.get('contract')!r} v{d.get('version')!r}")
    if not d.get("command_areas"):
        raise ValueError("module 3 hand-off has no command areas")
    for ca in d["command_areas"]:
        if len(ca["sustainable_m3"]) != 12 or ca["best_method"] not in EFFICIENCY:
            raise ValueError(f"command area {ca.get('source_id')}: bad water series or method")
    return d


# ------------------------------------------------------------------ production guides
@dataclass(frozen=True)
class GuideStep:
    start: date
    end: date
    what: str
    kind: str          # nursery | field | water | input | harvest | care


def crop_guide(crop: HighValueCrop, plant: tuple[int, int], method: str, et0_mm_day, year: int = 2026) -> list[GuideStep]:
    """A dated recipe card for one crop and planting date (template; adapt with extension agents)."""
    t0 = date(year if plant[0] >= 7 else year + 1, plant[0], plant[1])
    a, b, c, d = crop.stages
    steps = []
    if crop.nursery_days:
        steps.append(GuideStep(t0 - timedelta(crop.nursery_days), t0 - timedelta(1), "Raise seedlings in a shaded nursery bed", "nursery"))
    steps.append(GuideStep(t0 - timedelta(10), t0 - timedelta(1), "Prepare beds and lay drip lines" if method == "drip" else "Prepare beds and furrows", "field"))
    steps.append(GuideStep(t0, t0, "Transplant seedlings" if crop.nursery_days else "Plant", "field"))
    k = kc_curve(crop)
    for name, s, e in (("establishment", 0, a), ("development", a, a + b), ("mid-season", a + b, a + b + c), ("late season", a + b + c, a + b + c + d)):
        mm = float(np.mean(k[s:e]) * np.mean(et0_mm_day) * 7 / EFFICIENCY[method])
        steps.append(GuideStep(t0 + timedelta(s), t0 + timedelta(e - 1), f"Irrigate about {mm:.0f} mm a week ({name})", "water"))
    steps.append(GuideStep(t0, t0 + timedelta(3), "Basal fertilizer at planting (rate from soil test)", "input"))
    steps.append(GuideStep(t0 + timedelta(a + b // 2), t0 + timedelta(a + b // 2 + 3), "Top-dress nitrogen; weed", "input"))
    steps.append(GuideStep(t0 + timedelta(a), t0 + timedelta(a + b + c), "Scout weekly for pests and disease (stage 08 alerts)", "care"))
    steps.append(GuideStep(t0 + timedelta(a + b + c), t0 + timedelta(crop.field_days - 1), "Harvest at maturity; stop irrigation 10 to 14 days before", "harvest"))
    for n in crop.notes:
        steps.append(GuideStep(t0 + timedelta(crop.field_days), t0 + timedelta(crop.field_days + 14), n, "care"))
    return steps

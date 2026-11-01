"""
Domain model for Stage 03: Climate & Seasonal Intelligence.

Ubiquitous language
-------------------
DailyClimate     Daily rainfall and min/max temperature for one location over many years.
OnsetRule        The agronomic definition of "the rains have started" (a farmer's planting rain that
                 is not followed by a long dry spell). Season-specific (Meher, Belg).
SeasonRecord     What one year's season looked like: onset, cessation, length, total, longest dry spell.
ClimateOutlook   The output contract: probabilities a planner can act on (planting window, chance
                 that the season is long enough for a crop cycle, dry-spell and frost risk).

Analogy
-------
A bus timetable built from years of observations. Nobody knows exactly when tomorrow's bus
arrives, but after thirty years of records you can say "it comes before 9:10 in 8 days out of 10".
The outlook does the same for the rains.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np


@dataclass(frozen=True)
class OnsetRule:
    season: str = "meher"
    earliest_doy: int = 135          # 15 May: rains before this count as Belg, not Meher onset
    accum_mm: float = 20.0           # at least this much rain ...
    accum_days: int = 3              # ... within this many consecutive days
    rain_day_mm: float = 1.0         # a "rain day" threshold
    min_rain_days: int = 2           # rain days needed inside the accumulation window
    dry_spell_days: int = 7          # no dry spell longer than this ...
    check_window_days: int = 30      # ... within this many days after onset (false-start check)
    cessation_from_doy: int = 244    # 1 September: earliest possible end of season
    soil_capacity_mm: float = 100.0  # simple bucket for the end-of-season water balance
    evap_mm_day: float = 4.0

    def __post_init__(self) -> None:
        if self.accum_days < 1 or self.check_window_days < self.dry_spell_days:
            raise ValueError(f"Inconsistent onset rule: {self}")


@dataclass
class DailyClimate:
    station_id: str
    altitude_m: float
    start: date
    rain_mm: np.ndarray       # shape (years, 365)
    tmin_c: np.ndarray        # shape (years, 365)
    tmax_c: np.ndarray        # shape (years, 365)

    def __post_init__(self) -> None:
        shapes = {self.rain_mm.shape, self.tmin_c.shape, self.tmax_c.shape}
        if len(shapes) != 1 or self.rain_mm.ndim != 2 or self.rain_mm.shape[1] != 365:
            raise ValueError(f"Expected equal (years, 365) arrays, got {shapes}")
        if np.any(self.rain_mm < 0):
            raise ValueError("Negative rainfall values")

    @property
    def years(self) -> int:
        return self.rain_mm.shape[0]


@dataclass(frozen=True)
class SeasonRecord:
    year_index: int
    onset_doy: int | None          # None = no valid onset (failed season)
    cessation_doy: int | None
    length_days: int | None
    total_mm: float
    longest_dry_spell: int         # longest dry spell in the first 60 days after onset
    frost_days: int = 0


@dataclass(frozen=True)
class CropCycleFit:
    crop: str
    cycle_days: int
    probability: float             # share of years where season length >= cycle


@dataclass(frozen=True)
class ClimateOutlook:
    """Output contract to stages 01, 02, 04 and 08."""
    location_id: str
    season: str
    years_used: int
    onset_p20: str                 # "early" date: rains have started by now in 20% of years
    onset_p50: str
    onset_p80: str                 # by this date the rains have started in 80% of years
    cessation_p50: str
    length_p50_days: int
    failed_seasons_share: float
    dry_spell_risk: float          # share of years with a dry spell > 7 days in the 60 days after onset
    crop_cycle_fit: tuple[CropCycleFit, ...] = field(default_factory=tuple)
    frost_risk_by_altitude: dict = field(default_factory=dict)
    drought_years_share: float = 0.0   # share of years with seasonal SPI <= -1


def doy_to_label(doy: int | float | None) -> str:
    if doy is None or doy != doy:
        return "none"
    d = date(2025, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return d.strftime("%d %b")

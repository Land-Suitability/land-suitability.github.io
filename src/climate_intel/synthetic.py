"""
Synthetic daily weather generator (for demos and tests only).

Rain occurrence follows a two-state Markov chain whose wet-day probabilities follow the
Amhara highland seasonal cycle (small Belg bump around April, main Kiremt peak in July and
August). Amounts are gamma distributed. Each year gets a random onset shift and wetness factor,
so the generated climate has realistic year-to-year variability.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from .domain import DailyClimate


def _seasonal_wet_prob(doy: np.ndarray, shift: float) -> np.ndarray:
    kiremt = 0.80 * np.exp(-0.5 * ((doy - (214 + shift)) / 46.0) ** 2)
    belg = 0.22 * np.exp(-0.5 * ((doy - 105) / 22.0) ** 2)
    return np.clip(0.03 + kiremt + belg, 0, 0.92)


def generate(years: int = 30, altitude_m: float = 2000, seed: int = 42, station_id: str = "SYN-STATION") -> DailyClimate:
    if years < 1:
        raise ValueError("years must be >= 1")
    rng = np.random.default_rng(seed)
    doy = np.arange(1, 366)
    rain = np.zeros((years, 365))
    tmin = np.zeros((years, 365))
    tmax = np.zeros((years, 365))
    for y in range(years):
        shift = rng.normal(0, 9)                  # early or late season
        wet = rng.normal(1.0, 0.12)               # wetter or drier year
        p = np.clip(_seasonal_wet_prob(doy, shift) * wet, 0, 0.95)
        p_ww = np.clip(p + 0.15, 0, 0.97)          # persistence: wet after wet is more likely
        state = False
        for d in range(365):
            state = rng.random() < (p_ww[d] if state else p[d])
            if state:
                mean = 5.0 + 9.0 * p[d]
                rain[y, d] = rng.gamma(0.8, mean / 0.8)
        season = np.cos(2 * np.pi * (doy - 100) / 365)
        cloud = 2.5 * _seasonal_wet_prob(doy, shift)          # cloudy rainy-season nights stay mild
        tmin[y] = 9.5 + 1.5 * season + cloud - 1.5 * (rain[y] < 0.1) * (doy < 60) + rng.normal(0, 1.1, 365) - 0.0065 * (altitude_m - 2000)
        tmax[y] = 25.0 + 2.0 * season - 0.25 * np.minimum(rain[y], 20) + rng.normal(0, 1.2, 365) - 0.0065 * (altitude_m - 2000)
    return DailyClimate(station_id, altitude_m, date(1995, 1, 1), rain, tmin, tmax)

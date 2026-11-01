"""
Domain model for Stage 08: Monitoring, Forecasting & Risk.

Ubiquitous language
-------------------
NDVISeries       Vegetation index observations for one plot through the season (Sentinel-2, every ~5 days),
                 with cloud flags. Day 0 = planting (from stage 07).
CropCurve        The expected NDVI path of a healthy crop by days after planting (double logistic), with the
                 normal spread from past seasons.
Alert            A sustained departure below the expected curve, with severity and a cause hint
                 (widespread = weather; isolated = pest, disease or management).
YieldForecast    Expected cluster production with an interval that narrows as the season advances.

Analogy
-------
A child's growth chart at the clinic. The nurse does not judge one measurement alone; she plots it against
the normal curve for that age. Falling below the band twice in a row triggers a check-up. Stage 08 does
the same for every plot, every five days, from space.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class NDVISeries:
    plot_id: str
    crop: str
    days: np.ndarray            # days after planting
    ndvi: np.ndarray
    cloudy: np.ndarray          # bool

    def __post_init__(self) -> None:
        if not (len(self.days) == len(self.ndvi) == len(self.cloudy)):
            raise ValueError(f"{self.plot_id}: series arrays differ in length")
        if np.any(np.diff(self.days) <= 0):
            raise ValueError(f"{self.plot_id}: days must be strictly increasing")


@dataclass(frozen=True)
class CropCurve:
    """Double logistic: base + amp * (green-up sigmoid - senescence sigmoid)."""
    crop: str
    base: float = 0.18
    amp: float = 0.55
    up_mid: float = 35.0
    up_rate: float = 0.12
    down_mid: float = 105.0
    down_rate: float = 0.10
    sd: float = 0.05            # normal spread between healthy plots

    def expected(self, days) -> np.ndarray:
        d = np.asarray(days, dtype=float)
        return self.base + self.amp * (1 / (1 + np.exp(-self.up_rate * (d - self.up_mid)))
                                       - 1 / (1 + np.exp(-self.down_rate * (d - self.down_mid))))


@dataclass(frozen=True)
class Alert:
    plot_id: str
    day: int
    severity: str              # "watch" | "warning"
    z_score: float
    cause_hint: str


@dataclass(frozen=True)
class YieldForecast:
    cluster_id: str
    crop: str
    as_of_day: int
    method: str
    median_t: float
    low80_t: float
    high80_t: float

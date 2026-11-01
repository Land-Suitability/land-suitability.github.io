"""
Signal processing, alerts and yield forecasting.

  clean_and_smooth     drop cloudy points, interpolate to a daily grid, centred moving average
  anomalies            z-score of the smoothed series against the crop curve and its normal spread
  detect_alerts        sustained low z-scores -> alerts; cause hint from how widespread the problem is
  features             season-so-far features (integral, latest value, slope) for yield models
  fit_linear / forecast_linear   transparent baseline yield model with residual-based intervals
"""
from __future__ import annotations

import numpy as np

from .domain import Alert, CropCurve, NDVISeries

Z80 = 1.2816


def clean_and_smooth(s: NDVISeries, upto_day: int, window: int = 11) -> tuple[np.ndarray, np.ndarray]:
    ok = (~s.cloudy) & (s.days <= upto_day) & np.isfinite(s.ndvi)
    if ok.sum() < 3:
        raise ValueError(f"{s.plot_id}: fewer than 3 clear observations up to day {upto_day}")
    grid = np.arange(int(s.days[ok][0]), int(min(upto_day, s.days[ok][-1])) + 1)
    daily = np.interp(grid, s.days[ok], s.ndvi[ok])
    k = min(window, len(daily) // 2 * 2 + 1)
    pad = k // 2
    padded = np.pad(daily, pad, mode="edge")
    return grid, np.convolve(padded, np.ones(k) / k, mode="valid")


def anomalies(s: NDVISeries, curve: CropCurve, upto_day: int) -> tuple[np.ndarray, np.ndarray]:
    grid, sm = clean_and_smooth(s, upto_day)
    return grid, (sm - curve.expected(grid)) / curve.sd


def detect_alerts(series: list[NDVISeries], curve: CropCurve, as_of_day: int, z_watch: float = -1.5,
                  z_warn: float = -2.75, sustain_days: int = 10, widespread_share: float = 0.3) -> list[Alert]:
    """An alert needs the smoothed z-score below the threshold for `sustain_days` in a row."""
    flagged = []
    for s in series:
        grid, z = anomalies(s, curve, as_of_day)
        recent = z[-sustain_days:] if len(z) >= sustain_days else z
        if len(recent) == sustain_days and np.all(recent < z_watch):
            sev = "warning" if np.mean(recent) < z_warn else "watch"
            flagged.append((s.plot_id, sev, float(recent.mean())))
    share = len(flagged) / max(1, len(series))
    hint = ("widespread: likely weather (dry spell or waterlogging); check stage 03 rainfall"
            if share >= widespread_share else "isolated: check pests, disease, late weeding or top dressing (stage 07)")
    return [Alert(pid, as_of_day, sev, round(z, 2), hint) for pid, sev, z in flagged]


def features(s: NDVISeries, upto_day: int) -> np.ndarray:
    grid, sm = clean_and_smooth(s, upto_day)
    tail = sm[-15:]
    slope = float(np.polyfit(np.arange(len(tail)), tail, 1)[0]) if len(tail) > 2 else 0.0
    return np.array([float(np.trapezoid(sm, grid)) / 100.0, float(sm[-1]), slope * 100, float(sm.max())])


def fit_linear(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    if len(X) <= X.shape[1] + 1:
        raise ValueError("Not enough training seasons for the linear model")
    A = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ coef
    return coef, float(resid.std(ddof=A.shape[1]))


def forecast_linear(coef: np.ndarray, resid_sd: float, X: np.ndarray, areas: np.ndarray) -> tuple[float, float, float]:
    """Cluster production (t) = sum(area x yield); plot errors treated as partly shared (rho = 0.5)."""
    y = np.column_stack([np.ones(len(X)), X]) @ coef
    total = float(np.sum(np.maximum(y, 0) * areas))
    n = len(areas)
    rho = 0.5
    var = resid_sd ** 2 * (np.sum(areas ** 2) * (1 - rho) + rho * np.sum(areas) ** 2) if n else 0.0
    sd = float(np.sqrt(var))
    return total, total - Z80 * sd, total + Z80 * sd

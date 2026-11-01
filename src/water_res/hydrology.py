"""
Hydrology and crop-water calculations for Stage 02 (pure numpy, vectorised where useful).

  et0_hargreaves      reference evapotranspiration from temperature only (FAO-56 eq. 52),
                      used because full Penman-Monteith inputs are rarely available locally
  extraterrestrial_radiation   Ra from latitude and day of year (FAO-56 eqs. 21 to 25)
  kc_daily            FAO-56 single crop coefficient curve, day by day
  effective_rainfall  USDA-SCS monthly method (as used in FAO CROPWAT)
  irrigation_demand   monthly gross irrigation demand per hectare for an irrigated crop plan
"""
from __future__ import annotations

import calendar

import numpy as np

from .domain import IrrigatedCropPlan, MonthlySeries

GSC = 0.0820  # solar constant, MJ m-2 min-1
_DAYS = np.array([calendar.monthrange(2025, m)[1] for m in range(1, 13)])   # non-leap year
_MID_DOY = np.cumsum(_DAYS) - _DAYS / 2.0


def extraterrestrial_radiation(lat_deg: float, doy) -> np.ndarray:
    """Ra in MJ m-2 day-1 (FAO-56 eq. 21)."""
    doy = np.asarray(doy, dtype=float)
    if not -90 <= lat_deg <= 90:
        raise ValueError(f"Latitude out of range: {lat_deg}")
    phi = np.deg2rad(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi / 365 * doy)
    delta = 0.409 * np.sin(2 * np.pi / 365 * doy - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    return (24 * 60 / np.pi) * GSC * dr * (ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))


def et0_hargreaves(lat_deg: float, tmin: MonthlySeries, tmax: MonthlySeries) -> np.ndarray:
    """
    Monthly mean daily ET0 (mm/day). FAO-56 eq. 52:
        ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * 0.408 * Ra
    """
    tn, tx = np.array(tmin.values), np.array(tmax.values)
    if np.any(tx < tn):
        raise ValueError("Tmax is below Tmin in at least one month; check the input order")
    ra = extraterrestrial_radiation(lat_deg, _MID_DOY)
    tmean = (tn + tx) / 2.0
    return 0.0023 * (tmean + 17.8) * np.sqrt(tx - tn) * 0.408 * ra


def kc_daily(plan: IrrigatedCropPlan) -> np.ndarray:
    """Daily Kc over the season (length = season_days), FAO-56 piecewise linear curve."""
    c = plan.crop
    ini = np.full(c.l_ini, c.kc_ini)
    dev = np.linspace(c.kc_ini, c.kc_mid, c.l_dev + 1)[1:]
    mid = np.full(c.l_mid, c.kc_mid)
    late = np.linspace(c.kc_mid, c.kc_end, c.l_late + 1)[1:]
    return np.concatenate([ini, dev, mid, late])


def effective_rainfall(p_month_mm) -> np.ndarray:
    """USDA-SCS (CROPWAT) monthly effective rainfall in mm."""
    p = np.asarray(p_month_mm, dtype=float)
    if np.any(p < 0):
        raise ValueError("Negative rainfall")
    return np.where(p <= 250, p * (125 - 0.2 * p) / 125, 125 + 0.1 * p)


def irrigation_demand(plan: IrrigatedCropPlan, et0_mm_day: np.ndarray, rain_mm: MonthlySeries) -> dict:
    """
    Monthly crop water use and irrigation demand for 1 ha of the plan.

    Returns dict with arrays of length 12 (Jan..Dec):
      etc_mm     crop evapotranspiration in each month (only days the crop is in the field)
      peff_mm    effective rainfall credited to those days
      net_mm     net irrigation requirement = max(ETc - Peff, 0)
      gross_m3   gross demand per ha = net / efficiency * 10 (1 mm over 1 ha = 10 m3)
    The season may run across the new year (e.g. planted in November).
    """
    if not 1 <= plan.planting_month <= 12:
        raise ValueError(f"planting_month must be 1..12, got {plan.planting_month}")
    kc = kc_daily(plan)
    start_doy = int(np.sum(_DAYS[: plan.planting_month - 1])) + plan.planting_day - 1   # 0-based
    month_of_day = np.repeat(np.arange(12), _DAYS)                                       # 365 entries
    etc = np.zeros(12)
    days_in_field = np.zeros(12)
    for d, k in enumerate(kc):
        m = month_of_day[(start_doy + d) % 365]
        etc[m] += et0_mm_day[m] * k
        days_in_field[m] += 1
    peff_full = effective_rainfall(rain_mm.values)
    peff = peff_full * days_in_field / _DAYS          # credit rain only for days the crop is there
    net = np.maximum(etc - peff, 0.0)
    gross_m3 = net / plan.method.efficiency * 10.0
    return {"etc_mm": etc, "peff_mm": peff, "net_mm": net, "gross_m3": gross_m3, "days": days_in_field}

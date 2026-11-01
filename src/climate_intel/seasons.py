"""
Season analytics: onset, cessation, dry spells, frost, SPI and the planning outlook.

Methods follow common practice in East African agro-climatology:
  * onset      first day after `earliest_doy` with >= 20 mm in 3 days on >= 2 rain days, and no dry
               spell longer than 7 days in the next 30 days (protects against false starts)
  * cessation  first day after 1 September when a 100 mm soil bucket, drained at 4 mm/day, is empty
  * SPI        seasonal rainfall total transformed through a fitted gamma distribution to N(0, 1)
"""
from __future__ import annotations

import math

import numpy as np

from .domain import ClimateOutlook, CropCycleFit, DailyClimate, OnsetRule, SeasonRecord, doy_to_label


def longest_dry_spell(rain: np.ndarray, threshold: float = 1.0) -> int:
    best = run = 0
    for r in rain:
        run = run + 1 if r < threshold else 0
        best = max(best, run)
    return best


def detect_onset(rain_year: np.ndarray, rule: OnsetRule) -> int | None:
    """Return the onset day of year (1-based) or None if no valid onset occurs."""
    start = rule.earliest_doy - 1
    last = 365 - rule.check_window_days - rule.accum_days
    for d in range(start, last):
        window = rain_year[d:d + rule.accum_days]
        if window[0] < rule.rain_day_mm:          # onset is a rainy day, never the dry day before it
            continue
        if window.sum() < rule.accum_mm or (window >= rule.rain_day_mm).sum() < rule.min_rain_days:
            continue
        after = rain_year[d + rule.accum_days:d + rule.accum_days + rule.check_window_days]
        if longest_dry_spell(after, rule.rain_day_mm) <= rule.dry_spell_days:
            return d + 1
    return None


def detect_cessation(rain_year: np.ndarray, rule: OnsetRule) -> int | None:
    """Simple bucket water balance; season ends when the bucket empties after the cutoff date."""
    sw = 0.0
    for d in range(365):
        sw = min(rule.soil_capacity_mm, max(0.0, sw + rain_year[d] - rule.evap_mm_day))
        if d + 1 >= rule.cessation_from_doy and sw <= 0.0:
            return d + 1
    return None


def season_records(clim: DailyClimate, rule: OnsetRule, frost_c: float = 2.0,
                   at_altitude_m: float | None = None, lapse_c_per_m: float = 0.0065) -> list[SeasonRecord]:
    """One SeasonRecord per year. Frost days are counted at `at_altitude_m` using a lapse rate."""
    dz = 0.0 if at_altitude_m is None else at_altitude_m - clim.altitude_m
    out = []
    for y in range(clim.years):
        r = clim.rain_mm[y]
        on = detect_onset(r, rule)
        ce = detect_cessation(r, rule)
        if on is not None and ce is not None and ce > on:
            length = ce - on
            seg = r[on - 1:ce - 1]
            frost = int((clim.tmin_c[y, on - 1:ce - 1] - lapse_c_per_m * dz < frost_c).sum())
        else:
            length, seg, frost = None, r[rule.earliest_doy - 1:rule.cessation_from_doy + 30], 0
        # dry spells matter most during crop establishment: the first 60 days after onset
        out.append(SeasonRecord(y, on, ce if length else None, length, float(seg.sum()),
                                longest_dry_spell(seg[:60]), frost))
    return out


def spi(totals: np.ndarray) -> np.ndarray:
    """Standardised Precipitation Index of seasonal totals (gamma fit by Thom's approximation)."""
    x = np.asarray(totals, dtype=float)
    if x.size < 10:
        raise ValueError(f"SPI needs at least 10 years, got {x.size}")
    pos = x[x > 0]
    q = (x == 0).mean()
    a = math.log(pos.mean()) - np.log(pos).mean()
    alpha = (1 + math.sqrt(1 + 4 * a / 3)) / (4 * a)
    beta = pos.mean() / alpha
    try:
        from scipy.special import gammainc, ndtri
    except ImportError as e:
        raise ImportError("SPI needs scipy (pip install scipy)") from e
    cdf = q + (1 - q) * gammainc(alpha, np.where(x > 0, x, 0) / beta)
    return ndtri(np.clip(cdf, 1e-6, 1 - 1e-6))


def onset_cdf(records: list[SeasonRecord], doys: np.ndarray) -> np.ndarray:
    """Share of years in which the rains have started by each day of year (failed years never start)."""
    on = np.array([r.onset_doy if r.onset_doy is not None else 10_000 for r in records])
    return np.array([(on <= d).mean() for d in doys])


def build_outlook(clim: DailyClimate, rule: OnsetRule, crops: dict[str, int],
                  frost_altitudes: list[float] | None = None, location_id: str = "") -> ClimateOutlook:
    recs = season_records(clim, rule)
    valid = [r for r in recs if r.length_days is not None]
    if len(valid) < 5:
        raise ValueError(f"Only {len(valid)} valid seasons; cannot build a reliable outlook")
    onsets = np.array([r.onset_doy for r in valid])
    ces = np.array([r.cessation_doy for r in valid])
    lengths = np.array([r.length_days for r in valid])
    all_lengths = np.array([r.length_days or 0 for r in recs])
    fit = tuple(CropCycleFit(c, d, float((all_lengths >= d).mean())) for c, d in crops.items())
    dry = float(np.mean([r.longest_dry_spell > 7 for r in valid]))
    frost = {}
    for alt in frost_altitudes or []:
        fr = season_records(clim, rule, at_altitude_m=alt)
        frost[int(alt)] = float(np.mean([r.frost_days > 0 for r in fr]))
    s = spi(np.array([r.total_mm for r in recs]))
    return ClimateOutlook(
        location_id=location_id or clim.station_id, season=rule.season, years_used=clim.years,
        onset_p20=doy_to_label(np.percentile(onsets, 20)), onset_p50=doy_to_label(np.percentile(onsets, 50)),
        onset_p80=doy_to_label(np.percentile(onsets, 80)), cessation_p50=doy_to_label(np.median(ces)),
        length_p50_days=int(np.median(lengths)), failed_seasons_share=1 - len(valid) / len(recs),
        dry_spell_risk=dry, crop_cycle_fit=fit, frost_risk_by_altitude=frost,
        drought_years_share=float((s <= -1).mean()),
    )

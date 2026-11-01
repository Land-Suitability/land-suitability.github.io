"""
Factor catalogue and INDICATIVE crop requirement profiles for the Amhara pilot.

IMPORTANT: The thresholds below are indicative starting values compiled from general
crop-ecology guidance (FAO land evaluation practice and Ethiopian agronomic literature).
They are placeholders to be calibrated with regional research institutes and local
variety trials before any recommendation reaches a farmer.
"""
from __future__ import annotations

from .domain import ClassBreaks, CropProfile, CropRequirement, Direction, LandFactor, Season

INF = float("inf")

# ------------------------------------------------------------------ factor catalogue
ALTITUDE = LandFactor("altitude_m", "Altitude", "m a.s.l.", Direction.RANGE)
SLOPE = LandFactor("slope_pct", "Slope", "%", Direction.LOWER_IS_BETTER)
RAINFALL = LandFactor("rain_season_mm", "Growing-season rainfall", "mm", Direction.RANGE)
TEMPERATURE = LandFactor("temp_mean_c", "Mean growing-season temperature", "°C", Direction.RANGE)
SOIL_PH = LandFactor("soil_ph", "Soil pH (H2O)", "pH", Direction.RANGE)
SOIL_DEPTH = LandFactor("soil_depth_cm", "Effective soil depth", "cm", Direction.HIGHER_IS_BETTER)
DRAINAGE = LandFactor("drainage_class", "Drainage (1 very poor to 5 well drained)", "class", Direction.RANGE)
ORGANIC_C = LandFactor("soc_pct", "Soil organic carbon", "%", Direction.HIGHER_IS_BETTER)

FACTORS = {f.code: f for f in [ALTITUDE, SLOPE, RAINFALL, TEMPERATURE, SOIL_PH, SOIL_DEPTH, DRAINAGE, ORGANIC_C]}

_NOTE = "indicative; calibrate with regional research trials"


def _r(crop, factor, weight, **breaks) -> CropRequirement:
    return CropRequirement(crop=crop, factor=factor, breaks=ClassBreaks(**breaks), weight=weight, note=_NOTE)


TEFF_MEHER = CropProfile("teff", Season.MEHER, (
    _r("teff", ALTITUDE, 0.12, s1_low=1700, s1_high=2400, s2_low=1400, s2_high=2700, s3_low=1000, s3_high=3000),
    _r("teff", RAINFALL, 0.22, s1_low=450, s1_high=1000, s2_low=350, s2_high=1300, s3_low=300, s3_high=1600),
    _r("teff", TEMPERATURE, 0.16, s1_low=16, s1_high=24, s2_low=13, s2_high=27, s3_low=10, s3_high=30),
    _r("teff", SLOPE, 0.18, **{"s1_high": 8, "s2_high": 15, "s3_high": 30}),
    _r("teff", SOIL_PH, 0.10, s1_low=5.5, s1_high=7.5, s2_low=5.0, s2_high=8.0, s3_low=4.5, s3_high=8.5),
    # teff tolerates poorly drained Vertisols better than most cereals
    _r("teff", DRAINAGE, 0.08, s1_low=2, s1_high=5, s2_low=1.5, s2_high=5, s3_low=1, s3_high=5),
    _r("teff", SOIL_DEPTH, 0.08, s1_low=50, s2_low=30, s3_low=20),
    _r("teff", ORGANIC_C, 0.06, s1_low=1.5, s2_low=0.8, s3_low=0.4),
))

WHEAT_MEHER = CropProfile("bread_wheat", Season.MEHER, (
    _r("bread_wheat", ALTITUDE, 0.14, s1_low=1900, s1_high=2800, s2_low=1600, s2_high=3000, s3_low=1400, s3_high=3300),
    _r("bread_wheat", RAINFALL, 0.18, s1_low=500, s1_high=900, s2_low=400, s2_high=1100, s3_low=300, s3_high=1400),
    _r("bread_wheat", TEMPERATURE, 0.16, s1_low=12, s1_high=22, s2_low=10, s2_high=25, s3_low=7, s3_high=28),
    _r("bread_wheat", SLOPE, 0.16, **{"s1_high": 8, "s2_high": 15, "s3_high": 30}),
    _r("bread_wheat", SOIL_PH, 0.12, s1_low=6.0, s1_high=7.5, s2_low=5.5, s2_high=8.0, s3_low=5.0, s3_high=8.5),
    _r("bread_wheat", DRAINAGE, 0.12, s1_low=4, s1_high=5, s2_low=3, s2_high=5, s3_low=2, s3_high=5),
    _r("bread_wheat", SOIL_DEPTH, 0.07, s1_low=75, s2_low=50, s3_low=25),
    _r("bread_wheat", ORGANIC_C, 0.05, s1_low=1.5, s2_low=0.8, s3_low=0.4),
))

MAIZE_MEHER = CropProfile("maize", Season.MEHER, (
    _r("maize", ALTITUDE, 0.12, s1_low=1500, s1_high=2200, s2_low=1000, s2_high=2400, s3_low=500, s3_high=2700),
    _r("maize", RAINFALL, 0.20, s1_low=700, s1_high=1200, s2_low=550, s2_high=1500, s3_low=400, s3_high=1800),
    _r("maize", TEMPERATURE, 0.16, s1_low=18, s1_high=28, s2_low=15, s2_high=32, s3_low=12, s3_high=35),
    _r("maize", SLOPE, 0.16, **{"s1_high": 8, "s2_high": 15, "s3_high": 30}),
    _r("maize", SOIL_PH, 0.12, s1_low=5.5, s1_high=7.5, s2_low=5.0, s2_high=8.0, s3_low=4.5, s3_high=8.5),
    _r("maize", DRAINAGE, 0.10, s1_low=4, s1_high=5, s2_low=3, s2_high=5, s3_low=2, s3_high=5),
    _r("maize", SOIL_DEPTH, 0.08, s1_low=75, s2_low=50, s3_low=30),
    _r("maize", ORGANIC_C, 0.06, s1_low=1.5, s2_low=0.8, s3_low=0.4),
))

PROFILES = {p.crop: p for p in [TEFF_MEHER, WHEAT_MEHER, MAIZE_MEHER]}

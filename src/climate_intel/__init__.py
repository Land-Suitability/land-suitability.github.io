"""Stage 03: Climate & Seasonal Intelligence (Amhara Integrated Agriculture Ecosystem)."""
from .domain import ClimateOutlook, CropCycleFit, DailyClimate, OnsetRule, SeasonRecord, doy_to_label
from .seasons import (build_outlook, detect_cessation, detect_onset, longest_dry_spell, onset_cdf,
                      season_records, spi)
from .synthetic import generate

__all__ = ["ClimateOutlook", "CropCycleFit", "DailyClimate", "OnsetRule", "SeasonRecord", "doy_to_label",
           "build_outlook", "detect_cessation", "detect_onset", "longest_dry_spell", "onset_cdf",
           "season_records", "spi", "generate"]

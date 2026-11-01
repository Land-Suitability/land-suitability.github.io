#!/usr/bin/env python3
"""
Stage 03 demo on SYNTHETIC weather (30 generated years, not real station data).

  1. Detect Meher onset, cessation and season length for every year
  2. Build the planning outlook: onset percentiles, crop-cycle fit, dry-spell, frost and drought risk
  3. Write assets/demo-climate.json for the charts on the stage page

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from climate_intel import OnsetRule, build_outlook, doy_to_label, generate, onset_cdf, season_records, spi  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CROPS = {"teff (early)": 90, "teff (late)": 120, "bread wheat": 130, "maize (mid)": 150}


def main() -> int:
    try:
        clim = generate(years=30, altitude_m=2000, seed=42)
        rule = OnsetRule()
        recs = season_records(clim, rule)
        print("== 1. Season by season (first 8 of 30 years) ==")
        for r in recs[:8]:
            print(f"  year {r.year_index + 1:2d}: onset {doy_to_label(r.onset_doy):>7s}  end {doy_to_label(r.cessation_doy):>7s}"
                  f"  length {str(r.length_days):>4s} d  total {r.total_mm:6.0f} mm  longest dry spell {r.longest_dry_spell:2d} d")

        out = build_outlook(clim, rule, CROPS, frost_altitudes=[2000, 2600, 3000, 3300], location_id="CLUSTER-DEMO")
        print("\n== 2. Outlook ==")
        print(f"  onset: 20% of years by {out.onset_p20}, median {out.onset_p50}, 80% by {out.onset_p80}")
        print(f"  median end {out.cessation_p50}, median length {out.length_p50_days} days, failed seasons {out.failed_seasons_share:.0%}")
        print(f"  dry spell > 7 days in the 60 days after onset in {out.dry_spell_risk:.0%} of years; drought (SPI <= -1) in {out.drought_years_share:.0%}")
        for f in out.crop_cycle_fit:
            print(f"  {f.crop:14s} needs {f.cycle_days:3d} days -> season long enough in {f.probability:.0%} of years")
        for alt, p in out.frost_risk_by_altitude.items():
            print(f"  [DEBUG] frost (Tmin < 2 C) during the season at {alt} m: {p:.0%} of years")

        doys = np.arange(140, 232, 7)
        cdf = onset_cdf(recs, doys)
        s = spi(np.array([r.total_mm for r in recs]))
        data = {
            "onset_cdf": {"labels": [doy_to_label(d) for d in doys], "share": [round(float(c) * 100, 1) for c in cdf]},
            "crop_fit": {"crops": [f.crop for f in out.crop_cycle_fit], "pct": [round(f.probability * 100, 1) for f in out.crop_cycle_fit]},
            "frost": {str(k): round(v * 100, 1) for k, v in out.frost_risk_by_altitude.items()},
            "spi": [round(float(x), 2) for x in s],
            "outlook": {k: v for k, v in out.__dict__.items() if k not in ("crop_cycle_fit", "frost_risk_by_altitude")},
        }
        path = ROOT / "assets" / "demo-climate.json"
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"  [DEBUG] wrote {path.relative_to(ROOT)}")
        return 0
    except (KeyError, ValueError) as e:
        print(f"[DATA ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

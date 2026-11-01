#!/usr/bin/env python3
"""
Stage 05 demo on SYNTHETIC prices (generated series, not real market data).

  1. Fit a seasonal price model with an inflation trend to 6 years of monthly wheat prices
  2. Forecast the April price at contract signing in September (7 months ahead)
  3. Compare contract designs (fixed, fixed + advance, band, spot) for honouring and farmer income
  4. Build the DemandSignal for stage 04
Writes assets/demo-market.json for the charts.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from market_intel import (Buyer, BuyerType, OfftakeContract, PriceObservation, PriceRule, RuleKind,  # noqa: E402
                          band_around, contract_outcomes, demand_signal, fit_price_model, forecast)

ROOT = Path(__file__).resolve().parent.parent
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def synthetic_prices(seed: int = 5) -> list[PriceObservation]:
    """Wheat in a regional market (known up to September 2025): ~14%/year inflation, low after the Meher harvest, high in the lean season."""
    rng = np.random.default_rng(seed)
    season = np.array([-0.06, -0.04, -0.01, 0.02, 0.04, 0.07, 0.09, 0.08, 0.03, -0.02, -0.08, -0.09])
    obs = []
    months = [(y, m) for y in range(2020, 2026) for m in range(1, 13) if (y, m) <= (2025, 9)]   # known at signing
    for k, (y, m) in enumerate(months):
        p = 30_000 * np.exp(np.log(1.14) * k / 12 + season[m - 1] + rng.normal(0, 0.05))
        obs.append(PriceObservation("regional market", "wheat", y, m, float(p)))
    return obs


def main() -> int:
    try:
        obs = synthetic_prices()
        model = fit_price_model(obs)
        idx = model.seasonal_index()
        print("== 1. Price model ==")
        print(f"  trend {model.annual_trend:+.1%} per year, residual sd {model.resid_sd:.3f} (log)")
        print("  seasonal index: " + " ".join(f"{MONTHS[i]} {v:.2f}" for i, v in enumerate(idx)))

        fc = forecast(model, 2026, 4, issued=(2025, 9))
        print(f"\n== 2. Forecast April 2026, issued Sep 2025 (contract signing): median {fc.median:,.0f} birr/t (80% interval {fc.low80:,.0f} to {fc.high80:,.0f})")

        mill = Buyer("BUYER-MILL-01", BuyerType.FLOUR_MILL, "regional town")
        rules = {
            "Fixed price": (PriceRule(RuleKind.FIXED, fixed_price=fc.median), 0.0),
            "Fixed + 10% advance": (PriceRule(RuleKind.FIXED, fixed_price=fc.median), 0.10),
            "Band ±15%": (band_around(fc, 0.15), 0.0),
            "Spot (market price)": (PriceRule(RuleKind.SPOT), 0.0),
        }
        print("\n== 3. Contract designs for 900 t ==")
        results = {}
        for name, (rule, adv) in rules.items():
            c = OfftakeContract("C-" + name[:4], mill, "wheat", 900, "grade 2", 4, rule, advance_share=adv)
            r = contract_outcomes(c, fc)
            results[name] = r
            print(f"  {name:22s} honoured {r['honoured']:6.1%}  side-sell {r['side_sell']:5.1%}  walk-away {r['walk_away']:5.1%}"
                  f"  farmer mean {r['farmer_price_mean']:8,.0f}  farmer P10 {r['farmer_price_p10']:8,.0f}")

        c_band = OfftakeContract("C-BAND", mill, "wheat", 900, "grade 2", 4, band_around(fc, 0.15))
        sig = demand_signal([c_band], "wheat", spot_absorbable_t=500, planning_price=round(fc.median * 0.97))
        print(f"\n== 4. DemandSignal for stage 04: {sig}")

        hist = [o for o in obs if o.year >= 2024]
        labels = [f"{MONTHS[o.month - 1]} {str(o.year)[2:]}" for o in hist]
        fut = [(2025, m) for m in range(10, 13)] + [(2026, m) for m in range(1, 7)]
        fcs = [forecast(model, y, m, issued=(2025, 9)) for y, m in fut]
        labels += [f"{MONTHS[m - 1]} {str(y)[2:]}" for y, m in fut]
        nh = len(hist)
        out = {
            "labels": labels,
            "observed": [round(o.price_birr_t) for o in hist] + [None] * len(fut),
            "forecast": [None] * (nh - 1) + [round(hist[-1].price_birr_t)] + [round(f.median) for f in fcs],
            "low": [None] * nh + [round(f.low80) for f in fcs], "high": [None] * nh + [round(f.high80) for f in fcs],
            "seasonal_index": [round(float(v), 3) for v in idx], "trend": round(model.annual_trend, 3),
            "forecast_april": {"median": round(fc.median), "low80": round(fc.low80), "high80": round(fc.high80)},
            "contracts": {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in results.items()},
            "demand_signal": sig.__dict__,
        }
        path = ROOT / "assets" / "demo-market.json"
        path.write_text(json.dumps(out, indent=1), encoding="utf-8")
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

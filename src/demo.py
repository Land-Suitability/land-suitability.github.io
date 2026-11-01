#!/usr/bin/env python3
"""
Stage 12 demo on SYNTHETIC deliveries, payments and households (no real buyers or farmers).

  1. Settle three teff lot deliveries under a band contract (stage 05) with grade premiums and deductions
  2. Pay households in proportion to their kilograms in each lot; measure on-time payment
  3. Impact: difference-in-differences of household net income, pilot versus comparison kebeles
  4. Learning loop: realised yield by suitability class, sent back to stage 01
Writes assets/demo-distribution.json for the charts.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from distribution import (Delivery, GradeTerms, HouseholdOutcome, LearningSignal, diff_in_diff, pay_households,  # noqa: E402
                          payment_timeliness, settle, yields_by_class)

ROOT = Path(__file__).resolve().parent.parent
TERMS = GradeTerms({"grade 1": 1.05, "grade 2": 1.0, "grade 3": 0.93}, moisture_limit=12.5, foreign_limit=2.0)
BAND = (81_000, 109_000)          # floor and ceiling around a 95,000 birr/t teff forecast


def band_price(market: float) -> float:
    return min(max(market, BAND[0]), BAND[1])


def main() -> int:
    try:
        rng = np.random.default_rng(12)
        market = 101_500
        price = band_price(market)
        print(f"== 1. Settlement (market {market:,} birr/t -> band contract price {price:,} birr/t)")
        deliveries = [Delivery("DLV-001", "C-BAND-TEFF", "LOT-A-TEFF-2026-W43-001", date(2026, 11, 10), 9_468, 12.4, 0.6, "grade 1"),
                      Delivery("DLV-002", "C-BAND-TEFF", "LOT-A-TEFF-2026-W43-002", date(2026, 11, 10), 7_923, 12.5, 1.8, "grade 2"),
                      Delivery("DLV-003", "C-BAND-TEFF", "LOT-A-TEFF-2026-W44-005", date(2026, 11, 17), 9_120, 13.6, 2.6, "grade 3")]
        settlements = [settle(d, price, TERMS) for d in deliveries]
        for s in settlements:
            print(f"  {s.lot_id}: payable {s.payable_kg:7,.0f} kg x {s.price_birr_t:8,.0f} = gross {s.gross_birr:9,.0f}, "
                  f"deductions {s.deductions_birr:7,.0f}, fee {s.fee_birr:6,.0f}, net {s.net_birr:9,.0f} birr")

        print("\n== 2. Payments to households")
        payments, delivered = [], {d.lot_id: d.delivered_on for d in deliveries}
        for s, d in zip(settlements, deliveries):
            n = int(rng.integers(7, 12))
            kg = rng.dirichlet(np.ones(n)) * d.weight_kg
            hh = {f"HH-{d.lot_id[-3:]}-{i:02d}": float(k) for i, k in enumerate(kg)}
            delay = {h: d.delivered_on + timedelta(days=int(rng.integers(4, 12 if d.delivery_id != "DLV-003" else 25))) for h in hh}
            payments += pay_households(s, hh, delay)
        print(f"  {len(payments)} household payments, total {sum(p.amount_birr for p in payments):,.0f} birr "
              f"(equals net settlements: {abs(sum(p.amount_birr for p in payments) - sum(s.net_birr for s in settlements)) < 1:})")
        ontime = payment_timeliness(payments, delivered, 14)
        print(f"  paid within 14 days: {ontime:.0%}")

        print("\n== 3. Impact on household net income (difference-in-differences)")
        rows = []
        for g, n, effect in (("pilot", 300, 9_000), ("comparison", 300, 0)):
            base = rng.lognormal(np.log(38_000), 0.35, n)
            trend = 1.14                               # inflation and general change, common to both groups
            end = base * trend + effect + rng.normal(0, 6_000, n)
            rows += [HouseholdOutcome(f"{g[0].upper()}{i:03d}", g, float(b), float(e)) for i, (b, e) in enumerate(zip(base, end))]
        imp = diff_in_diff(rows)
        pb = np.mean([r.baseline_birr for r in rows if r.group == "pilot"]); pe = np.mean([r.endline_birr for r in rows if r.group == "pilot"])
        cb = np.mean([r.baseline_birr for r in rows if r.group == "comparison"]); ce = np.mean([r.endline_birr for r in rows if r.group == "comparison"])
        print(f"  pilot change {imp.pilot_change:+,.0f}, comparison change {imp.comparison_change:+,.0f} -> effect "
              f"{imp.effect_birr:+,.0f} birr per household (95% CI {imp.low95:,.0f} to {imp.high95:,.0f})")
        print(f"  [DEBUG] naive before/after for the pilot alone would claim {pe - pb:+,.0f}: inflation is not impact")

        print("\n== 4. Learning loop: realised teff yield by stage 01 suitability class")
        recs = [(c, max(0.2, rng.normal(m, 0.25))) for c, m, n in (("S1", 1.95, 90), ("S2", 1.6, 70), ("S3", 0.85, 25)) for _ in range(n)]
        ybc = yields_by_class(recs)
        predicted = {"S1": 2.0 * 0.95, "S2": 2.0 * 0.80, "S3": 2.0 * 0.55}
        for c in ybc:
            print(f"  {c}: realised {ybc[c]:.2f} t/ha vs predicted {predicted[c]:.2f}  -> {'ok' if abs(ybc[c] / predicted[c] - 1) < 0.1 else 'recalibrate'}")
        sig = LearningSignal(ybc, realised_price_birr_t=price, on_time_payment_share=ontime, buyer_rating=4.2)
        print(f"  [DEBUG] learning signal: {sig}")

        out = {"settlements": [s.__dict__ for s in settlements], "price": price, "market": market,
               "ontime": round(ontime, 3), "n_payments": len(payments),
               "did": {"pilot": [round(pb), round(pe)], "comparison": [round(cb), round(ce)],
                       "counterfactual": [round(pb), round(pb + imp.comparison_change)],
                       "effect": round(imp.effect_birr), "low": round(imp.low95), "high": round(imp.high95), "naive": round(pe - pb)},
               "yields": {"classes": list(ybc), "realised": [round(ybc[c], 2) for c in ybc], "predicted": [round(predicted[c], 2) for c in ybc]},
               "signal": {"realised_price_birr_t": price, "on_time_payment_share": round(ontime, 2), "buyer_rating": 4.2,
                          "yields_by_class": {k: round(v, 2) for k, v in ybc.items()}}}
        path = ROOT / "assets" / "demo-distribution.json"
        path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
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

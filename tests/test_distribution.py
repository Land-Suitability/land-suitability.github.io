"""Tests for Stage 12. Run: python3 -m pytest tests  (or python3 tests/test_distribution.py)"""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from distribution import (Delivery, GradeTerms, HouseholdOutcome, diff_in_diff, pay_households, payment_timeliness,  # noqa: E402
                          settle, yields_by_class)

TERMS = GradeTerms({"g1": 1.05, "g2": 1.0}, moisture_limit=12.5, foreign_limit=2.0, service_fee=0.03)
D0 = date(2026, 11, 10)


def test_settlement_premium_and_fee():
    s = settle(Delivery("D", "C", "L", D0, 10_000, 12.0, 1.0, "g1"), 100_000, TERMS)
    assert s.deductions_birr == 0 and abs(s.gross_birr - 1_050_000) < 1e-6 and abs(s.net_birr - 1_050_000 * 0.97) < 1e-6


def test_settlement_deducts_excess_moisture_and_foreign():
    s = settle(Delivery("D", "C", "L", D0, 10_000, 13.5, 3.0, "g2"), 100_000, TERMS)
    assert abs(s.payable_kg - 9_800) < 1e-6 and abs(s.deductions_birr - 20_000) < 1e-6


def test_unknown_grade_rejected():
    try:
        settle(Delivery("D", "C", "L", D0, 1000, 12, 1, "g9"), 100_000, TERMS)
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_household_payments_sum_and_proportion():
    s = settle(Delivery("D", "C", "L", D0, 1000, 12, 1, "g2"), 100_000, TERMS)
    pays = pay_households(s, {"H1": 750, "H2": 250}, {"H1": D0 + timedelta(days=5), "H2": D0 + timedelta(days=20)})
    assert abs(sum(p.amount_birr for p in pays) - s.net_birr) < 1e-6 and abs(pays[0].amount_birr / pays[1].amount_birr - 3) < 1e-9
    assert payment_timeliness(pays, {"L": D0}, 14) == 0.5


def test_did_removes_common_trend():
    rng = np.random.default_rng(0)
    rows = []
    for g, eff in (("pilot", 5000), ("comparison", 0)):
        b = rng.normal(40_000, 5_000, 200)
        rows += [HouseholdOutcome(f"{g}{i}", g, x, x * 1.2 + eff + rng.normal(0, 1000)) for i, x in enumerate(b)]
    imp = diff_in_diff(rows)
    assert imp.low95 < 5000 < imp.high95 and abs(imp.effect_birr - 5000) < 1000


def test_yields_by_class():
    assert yields_by_class([("S1", 2.0), ("S1", 1.0), ("S2", 1.0)]) == {"S1": 1.5, "S2": 1.0}


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"[PASS] {name}")
            except Exception as e:
                failures += 1
                print(f"[FAIL] {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failures else 0)

"""Tests for Stage 05. Run: python3 -m pytest tests  (or python3 tests/test_market.py)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from market_intel import (Buyer, BuyerType, OfftakeContract, PriceForecast, PriceObservation, PriceRule, RuleKind,  # noqa: E402
                          band_around, contract_outcomes, demand_signal, fit_price_model, forecast)

BUYER = Buyer("B1", BuyerType.FLOUR_MILL, "town")


def series(trend=0.10, amp=0.08, noise=0.0, years=4):
    obs = []
    for k in range(years * 12):
        m = k % 12 + 1
        p = 1000 * np.exp(np.log(1 + trend) * k / 12 + amp * np.cos(2 * np.pi * (m - 7) / 12))
        obs.append(PriceObservation("mkt", "wheat", 2020 + k // 12, m, float(p)))
    return obs


def test_model_recovers_trend_and_season():
    m = fit_price_model(series())
    assert abs(m.annual_trend - 0.10) < 0.005
    idx = m.seasonal_index()
    assert idx.argmax() == 6 and idx.argmin() == 0       # July peak, January trough


def test_forecast_interval_widens_with_horizon():
    m = fit_price_model(series())
    near = forecast(m, 2024, 2, issued=(2024, 1))
    far = forecast(m, 2024, 8, issued=(2024, 1))
    assert (far.high80 / far.low80) > (near.high80 / near.low80)


def test_band_rule_clips():
    r = PriceRule(RuleKind.BAND, floor=90, ceiling=110)
    assert list(r.price([80, 100, 130])) == [90, 100, 110]


def test_invalid_rules_rejected():
    for kw in [dict(kind=RuleKind.FIXED), dict(kind=RuleKind.BAND, floor=100, ceiling=90)]:
        try:
            PriceRule(**kw)
        except ValueError:
            continue
        raise AssertionError(f"should reject {kw}")


def test_band_honoured_more_often_than_fixed():
    fc = PriceForecast("wheat", "mkt", 2026, 4, 1000, 800, 1250)
    fixed = contract_outcomes(OfftakeContract("F", BUYER, "wheat", 100, "g2", 4, PriceRule(RuleKind.FIXED, fixed_price=1000)), fc)
    band = contract_outcomes(OfftakeContract("B", BUYER, "wheat", 100, "g2", 4, band_around(fc, 0.15)), fc)
    adv = contract_outcomes(OfftakeContract("A", BUYER, "wheat", 100, "g2", 4, PriceRule(RuleKind.FIXED, fixed_price=1000),
                                            advance_share=0.1), fc)
    assert band["honoured"] > fixed["honoured"] and adv["side_sell"] < fixed["side_sell"]


def test_demand_signal_sums_contracts():
    rule = PriceRule(RuleKind.SPOT)
    cs = [OfftakeContract("1", BUYER, "wheat", 300, "g2", 4, rule), OfftakeContract("2", BUYER, "wheat", 200, "g2", 4, rule),
          OfftakeContract("3", BUYER, "teff", 50, "g1", 1, rule)]
    s = demand_signal(cs, "wheat", 100, 1000)
    assert (s.min_t, s.max_t) == (500, 600)


def test_short_history_rejected():
    try:
        fit_price_model(series(years=1))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


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

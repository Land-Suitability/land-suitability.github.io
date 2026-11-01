"""Tests for Stage 08. Run: python3 -m pytest tests  (or python3 tests/test_monitoring.py)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from monitoring import CropCurve, NDVISeries, clean_and_smooth, detect_alerts, features, fit_linear, forecast_linear  # noqa: E402

CURVE = CropCurve("teff")
DAYS = np.arange(0, 141, 5)


def series(pid, shift=0.0, cloudy_idx=()):
    v = CURVE.expected(DAYS) + shift
    cloudy = np.zeros(len(DAYS), bool)
    cloudy[list(cloudy_idx)] = True
    v = np.where(cloudy, v - 0.3, v)
    return NDVISeries(pid, "teff", DAYS.copy(), v, cloudy)


def test_curve_shape():
    e = CURVE.expected([0, 70, 140])
    assert e[1] > e[0] and e[1] > e[2] and 0.6 < e[1] < 0.8


def test_cloudy_points_are_ignored():
    _, clean = clean_and_smooth(series("A"), 140)
    _, cloudy = clean_and_smooth(series("A", cloudy_idx=[8, 9, 10]), 140)
    assert np.max(np.abs(clean - cloudy)) < 0.05


def test_validation_rejects_bad_series():
    try:
        NDVISeries("x", "teff", np.array([0, 5, 5]), np.zeros(3), np.zeros(3, bool))
    except ValueError:
        return
    raise AssertionError("non-increasing days should raise")


def test_isolated_stress_alert_and_hint():
    plots = [series(f"P{i}") for i in range(10)] + [series("S", shift=-0.2)]
    alerts = detect_alerts(plots, CURVE, as_of_day=70)
    assert [a.plot_id for a in alerts] == ["S"] and alerts[0].severity == "warning" and "isolated" in alerts[0].cause_hint


def test_widespread_stress_points_to_weather():
    plots = [series(f"P{i}", shift=-0.12) for i in range(10)]
    alerts = detect_alerts(plots, CURVE, as_of_day=70)
    assert len(alerts) == 10 and "weather" in alerts[0].cause_hint


def test_linear_forecast_recovers_relationship():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 2)); y = 1 + 2 * X[:, 0] - X[:, 1] + rng.normal(0, 0.1, 200)
    coef, sd = fit_linear(X, y)
    assert np.allclose(coef, [1, 2, -1], atol=0.05) and 0.05 < sd < 0.15
    total, lo, hi = forecast_linear(coef, sd, np.zeros((3, 2)), np.ones(3))
    assert abs(total - 3) < 0.2 and lo < total < hi


def test_features_finite():
    assert np.all(np.isfinite(features(series("A"), 60)))


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

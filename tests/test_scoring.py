"""Tests for the Stage 01 scoring engine. Run: python3 -m pytest tests  (or python3 tests/test_scoring.py)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from land_intel import ClassBreaks, Method, ahp_weights, assess_grid, score_factor  # noqa: E402
from land_intel.factors import PROFILES  # noqa: E402

SLOPE = ClassBreaks(s1_high=8, s2_high=15, s3_high=30)
PH = ClassBreaks(s1_low=6, s1_high=7.5, s2_low=5.5, s2_high=8, s3_low=5, s3_high=8.5)


def test_lower_is_better_classes():
    s, r = score_factor([2, 8, 12, 15, 25, 31], SLOPE)
    assert list(r) == [3, 3, 2, 2, 1, 0]
    assert s[0] == 1.0 and s[-1] == 0.0
    assert np.all(np.diff(s) <= 0), "score must not increase as slope increases"


def test_range_factor_both_sides():
    _, r = score_factor([4.8, 5.2, 5.8, 6.5, 7.8, 8.3, 9.0], PH)
    assert list(r) == [0, 1, 2, 3, 2, 1, 0]


def test_nan_is_missing_not_suitable():
    s, r = score_factor([np.nan, 5], SLOPE)
    assert np.isnan(s[0]) and r[0] == -1 and r[1] == 3


def test_invalid_breaks_rejected():
    try:
        ClassBreaks(s1_high=20, s2_high=10, s3_high=30)
    except ValueError:
        return
    raise AssertionError("non-nested breaks should raise")


def test_ahp_consistent_matrix():
    a = np.array([[1, 3, 5], [1 / 3, 1, 5 / 3], [1 / 5, 3 / 5, 1]])   # perfectly consistent
    w, cr = ahp_weights(a)
    assert np.allclose(w.sum(), 1) and cr < 1e-6
    assert np.allclose(w, np.array([15, 5, 3]) / 23, atol=1e-6)


def test_ahp_rejects_non_reciprocal():
    try:
        ahp_weights(np.array([[1, 2], [2, 1]]))
    except ValueError:
        return
    raise AssertionError("non-reciprocal matrix should raise")


def _uniform_layers(**overrides):
    base = {"altitude_m": 2200, "slope_pct": 3, "rain_season_mm": 800, "temp_mean_c": 18, "soil_ph": 6.5,
            "drainage_class": 4.5, "soil_depth_cm": 120, "soc_pct": 2.0}
    base.update(overrides)
    return {k: np.full((2, 2), float(v)) for k, v in base.items()}


def test_ideal_land_is_s1_for_wheat():
    out = assess_grid(_uniform_layers(), PROFILES["bread_wheat"], Method.AHP_WLC)
    assert np.all(out["rank"] == 3)


def test_any_n_factor_forces_n():
    out = assess_grid(_uniform_layers(slope_pct=40), PROFILES["bread_wheat"], Method.AHP_WLC)
    assert np.all(out["rank"] == 0)


def test_compensation_cap():
    # pH 5.2 is S3 for wheat; averaging alone would give S1, the cap limits it to S2
    out = assess_grid(_uniform_layers(soil_ph=5.2), PROFILES["bread_wheat"], Method.AHP_WLC)
    assert np.all(out["rank"] == 2)
    fao = assess_grid(_uniform_layers(soil_ph=5.2), PROFILES["bread_wheat"], Method.FAO_LIMITING)
    assert np.all(fao["rank"] == 1)


def test_teff_tolerates_poor_drainage_better_than_wheat():
    layers = _uniform_layers(drainage_class=2.2)
    teff = assess_grid(layers, PROFILES["teff"], Method.FAO_LIMITING)["rank"][0, 0]
    wheat = assess_grid(layers, PROFILES["bread_wheat"], Method.FAO_LIMITING)["rank"][0, 0]
    assert teff > wheat


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

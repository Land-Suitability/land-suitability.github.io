"""Tests for Stage 03. Run: python3 -m pytest tests  (or python3 tests/test_climate.py)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from climate_intel import (OnsetRule, build_outlook, detect_cessation, detect_onset, doy_to_label, generate,  # noqa: E402
                           longest_dry_spell, spi)

RULE = OnsetRule()


def year_with(events: dict) -> np.ndarray:
    r = np.zeros(365)
    for doy, mm in events.items():
        r[doy - 1] = mm
    return r


def test_longest_dry_spell():
    assert longest_dry_spell(np.array([0, 0, 5, 0, 0, 0, 2, 0])) == 3


def test_onset_detected_when_rains_continue():
    ev = {160: 12, 161: 10}
    ev.update({d: 6 for d in range(163, 230, 3)})        # rain every third day afterwards
    assert detect_onset(year_with(ev), RULE) == 160


def test_false_start_is_rejected():
    ev = {150: 15, 151: 10}                               # good rain, then 20 dry days
    ev.update({d: 6 for d in range(172, 260, 3)})
    ev.update({172: 12, 173: 10})
    assert detect_onset(year_with(ev), RULE) == 172


def test_rain_before_earliest_date_is_not_meher_onset():
    ev = {100: 30, 101: 30}
    assert detect_onset(year_with(ev), RULE) is None


def test_cessation_when_bucket_empties():
    ev = {d: 8 for d in range(150, 250)}                  # wet until day 249
    end = detect_cessation(year_with(ev), RULE)
    assert end is not None and 250 <= end <= 280


def test_spi_is_standardised():
    totals = np.random.default_rng(1).gamma(9, 90, 40)
    s = spi(totals)
    assert abs(s.mean()) < 0.3 and 0.7 < s.std() < 1.3


def test_outlook_on_synthetic_climate():
    out = build_outlook(generate(25, seed=3), RULE, {"short": 90, "long": 200}, frost_altitudes=[2000, 3300])
    fit = {f.crop: f.probability for f in out.crop_cycle_fit}
    assert fit["short"] >= fit["long"]
    assert out.frost_risk_by_altitude[3300] >= out.frost_risk_by_altitude[2000]
    assert doy_to_label(135) == "15 May"


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

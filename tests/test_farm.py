"""Tests for Stage 07. Run: python3 -m pytest tests  (or python3 tests/test_farm.py)"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from farm_ops import (FieldReport, Household, HouseholdPlot, OperationTemplate, adherence, assign_plots,  # noqa: E402
                      build_calendar, prioritise_visits)


def hh(hid, willing, plots):
    h = Household(hid, "K1", set(willing))
    h.plots = [HouseholdPlot(f"{hid}-{i}", hid, "K1", a, s) for i, (a, s) in enumerate(plots)]
    return h


def test_comparative_advantage_assignment():
    # plot X suits both crops, plot Y suits only teff: teff should go to Y so maize can use X
    households = [hh("H1", ["teff", "maize"], [(1.0, {"teff": 0.9, "maize": 0.8}), (1.0, {"teff": 0.85, "maize": 0.2})])]
    out, gaps = assign_plots(households, {"teff": 1.0, "maize": 1.0})
    got = {a.plot_id: a.option_id for a in out}
    assert got == {"H1-0": "maize", "H1-1": "teff"} and gaps == {"teff": 0.0, "maize": 0.0}


def test_unwilling_household_never_assigned():
    out, gaps = assign_plots([hh("H1", ["teff"], [(1.0, {"maize": 1.0, "teff": 0.6})])], {"maize": 1.0})
    assert out == [] and gaps["maize"] == 1.0


def test_calendar_with_repeats():
    a, _ = assign_plots([hh("H1", ["onion"], [(0.5, {"onion": 1.0})])], {"onion": 0.5})
    ops = build_calendar(a, [OperationTemplate("onion", "planting", 0, 5),
                             OperationTemplate("onion", "irrigation", 7, 2, repeat_every=7, repeat_until=28)], {"onion": date(2027, 1, 1)})
    assert [o.target.day for o in ops if o.code == "irrigation"] == [8, 15, 22, 29]


def test_adherence_counts_only_closed_windows_and_tolerance():
    a, _ = assign_plots([hh("H1", ["teff"], [(1.0, {"teff": 1.0})])], {"teff": 1.0})
    ops = build_calendar(a, [OperationTemplate("teff", "planting", 0, 5), OperationTemplate("teff", "top_dress", 60, 5)],
                         {"teff": date(2026, 7, 10)})
    reps = [FieldReport("H1-0", "planting", date(2026, 7, 20))]          # 10 days late
    adh = adherence(ops, reps, as_of=date(2026, 8, 1))                  # top dressing window still open
    assert adh["plot"]["H1-0"] == 0.0 and "top_dress" not in adh["code"]


def test_visits_rank_missing_steps_first():
    households = [hh("H1", ["teff"], [(1.0, {"teff": 1.0})]), hh("H2", ["teff"], [(1.0, {"teff": 1.0})])]
    a, _ = assign_plots(households, {"teff": 2.0})
    ops = build_calendar(a, [OperationTemplate("teff", "planting", 0, 5)], {"teff": date(2026, 7, 10)})
    reps = [FieldReport("H1-0", "planting", date(2026, 7, 20)), FieldReport("H2-0", "planting", None)]
    v = prioritise_visits(a, adherence(ops, reps, date(2026, 8, 1)), {"teff": 150_000}, capacity=2)
    assert v[0].plot_id == "H2-0" and len(v) == 2


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

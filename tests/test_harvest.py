"""Tests for Stage 09. Run: python3 -m pytest tests  (or python3 tests/test_harvest.py)"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from harvest import (GradeSpec, HarvestResource, MaturityWindow, dry_weight, field_loss_share, form_lots, grade_of,  # noqa: E402
                     schedule)

D0 = date(2026, 10, 20)
DAYS = tuple(D0 + timedelta(days=k) for k in range(30))


def w(pid, start, length, area=1.0):
    return MaturityWindow(pid, "A", "teff", area, area * 2, D0 + timedelta(days=start), D0 + timedelta(days=start + length))


def test_edf_beats_fifo_on_lateness():
    windows = [w("long", 0, 20), w("short", 0, 1)]           # requests: long-window plot asked first
    res = [HarvestResource("T", "thresher", 1.0, DAYS)]
    fifo = {j.plot_id: j for j in schedule(windows, res, "fifo")}
    edf = {j.plot_id: j for j in schedule(windows, res, "edf")}
    assert fifo["short"].days_late == 0 and fifo["short"].day == D0 + timedelta(days=1)
    assert edf["short"].day == D0 and edf["long"].days_late == 0


def test_capacity_shortage_raises():
    try:
        schedule([w("p", 0, 1, area=100)], [HarvestResource("T", "thresher", 1.0, DAYS[:5])])
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError")


def test_field_loss_grows_and_caps():
    assert field_loss_share(0) == 0.03 and field_loss_share(10) > field_loss_share(5) and field_loss_share(1000) == 0.35


def test_dry_weight_conserves_dry_matter():
    w1 = dry_weight(1000, 18, 12.5)
    assert abs(w1 * (1 - 0.125) - 1000 * (1 - 0.18)) < 1e-9


def test_dry_weight_rejects_wetting():
    try:
        dry_weight(1000, 10, 12)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_grading():
    specs = [GradeSpec("g1", 12.5, 1.0), GradeSpec("g2", 13.5, 2.0)]
    assert grade_of(12.0, 0.5, specs) == "g1" and grade_of(13.0, 0.5, specs) == "g2" and grade_of(15, 0.5, specs) == "below grade"


def test_lots_trace_plots_and_segregate():
    h = [{"plot_id": f"P{i}", "cluster_id": "A", "product": "teff", "day": D0, "kg": 4000, "moisture": 12.5,
          "foreign": 0.5 if i % 2 else 2.0, "floor": "tarp" if i % 2 else "ground"} for i in range(4)]
    mixed = form_lots(h, max_lot_kg=10_000)
    seg = form_lots(h, max_lot_kg=10_000, segregate_by="floor")
    assert sum(len(l.plot_ids) for l in mixed) == 4 and len(seg) == 2
    assert sorted(round(l.foreign, 2) for l in seg) == [0.5, 2.0]


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

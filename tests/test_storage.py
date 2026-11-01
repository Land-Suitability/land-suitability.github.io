"""Tests for Stage 10. Run: python3 -m pytest tests  (or python3 tests/test_storage.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from storage import CandidateSite, StorageTech, SupplyPoint, assign, locate_centres, simulate_inventory, store_or_sell  # noqa: E402

PTS = [SupplyPoint("W1", 0, 0, 100), SupplyPoint("W2", 1, 0, 100), SupplyPoint("E1", 20, 0, 100), SupplyPoint("E2", 21, 0, 100)]
SITES = [CandidateSite("W", 0.5, 0, 500, 0), CandidateSite("E", 20.5, 0, 500, 0), CandidateSite("M", 10.5, 0, 500, 0)]


def test_two_centres_split_east_and_west():
    centres, _ = locate_centres(PTS, SITES, 2)
    assert sorted(c.site.site_id for c in centres) == ["E", "W"]


def test_one_centre_in_the_middle():
    centres, _ = locate_centres(PTS, SITES, 1)
    assert centres[0].site.site_id == "M"


def test_capacity_respected_or_infeasible():
    small = [CandidateSite("W", 0.5, 0, 150, 0), CandidateSite("E", 20.5, 0, 150, 0)]
    assert assign(PTS, small)[0] == float("inf")
    try:
        locate_centres(PTS, small, 2)
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError")


def test_store_or_sell_flat_prices_never_pays():
    v = store_or_sell([1.0] * 12, 11, StorageTech("t", 0.02, 100), 1000, inflation_per_month=0.0)
    assert v[0] == 1000 and all(x < 1000 for x in v[1:])


def test_low_loss_storage_pays_when_prices_rise():
    idx = [1.0] * 12
    idx[4] = 1.3                               # May price 30% above November
    trad = store_or_sell(idx, 11, StorageTech("trad", 0.05, 10), 1000, inflation_per_month=0.0)
    herm = store_or_sell(idx, 11, StorageTech("herm", 0.004, 10), 1000, inflation_per_month=0.0)
    assert herm[6] > herm[0] and herm[6] > trad[6]


def test_inventory_over_capacity_weeks():
    stock, over = simulate_inventory([10, 10, 10, 0], [0, 0, 5, 20], capacity_t=15)
    assert list(stock) == [10, 20, 25, 5] and over == [1, 2]


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

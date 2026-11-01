"""Tests for Stage 06. Run: python3 -m pytest tests  (or python3 tests/test_inputs.py)"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from inputs import InputItem, InputNorm, Supplier, allocate, explode_plan, lead_quantile, order_by_date, p_on_time  # noqa: E402

NPS = InputItem("nps", "NPS", "kg")
S_FAST = Supplier("F", "agro_dealer", ("nps",), {"nps": 1_000}, {"nps": 90}, 10, 0.2)
S_SLOW = Supplier("S", "cooperative_union", ("nps",), {"nps": 100_000}, {"nps": 70}, 30, 0.5)


def test_explode_plan_quantities_and_dates():
    reqs = explode_plan([{"cluster_id": "A", "option_id": "w", "hectares": 10}],
                        [InputNorm("w", NPS, 150, -7), InputNorm("w", NPS, 50, 30, applies_share=0.5)], {"w": date(2026, 6, 20)})
    assert [(r.quantity, r.need_by) for r in reqs] == [(1500, date(2026, 6, 13)), (250, date(2026, 7, 20))]


def test_p_on_time_median_and_monotone():
    assert abs(p_on_time(S_SLOW, 30) - 0.5) < 1e-9
    assert p_on_time(S_SLOW, 60) > p_on_time(S_SLOW, 40) > p_on_time(S_SLOW, 20)
    assert p_on_time(S_SLOW, 0) == 0


def test_quantile_inverts_cdf():
    q = lead_quantile(S_SLOW, 0.9)
    assert abs(p_on_time(S_SLOW, q) - 0.9) < 1e-6


def test_order_by_date_meets_target():
    need = date(2026, 6, 1)
    ob = order_by_date(S_SLOW, need, 0.9)
    assert p_on_time(S_SLOW, (need - ob).days) >= 0.9


def test_allocation_prefers_reliable_then_splits_on_capacity():
    reqs = explode_plan([{"cluster_id": "A", "option_id": "w", "hectares": 10}], [InputNorm("w", NPS, 150, 0)], {"w": date(2026, 6, 1)})
    orders, warnings = allocate(reqs, [S_SLOW, S_FAST])
    assert [o.supplier_id for o in orders] == ["F", "S"] and orders[0].quantity == 1000 and orders[1].quantity == 500
    assert not warnings


def test_shortfall_and_late_warnings():
    reqs = explode_plan([{"cluster_id": "A", "option_id": "w", "hectares": 10}], [InputNorm("w", NPS, 150, 0)], {"w": date(2026, 6, 1)})
    _, warnings = allocate(reqs, [S_FAST], today=date(2026, 5, 30))
    assert any("Shortfall" in w for w in warnings) and any("order date passed" in w for w in warnings)


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

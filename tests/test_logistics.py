"""Tests for Stage 11. Run: python3 -m pytest tests  (or python3 tests/test_logistics.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from logistics import PickupRequest, Road, RoadNetwork, Vehicle, savings_routes, shortest_paths  # noqa: E402

NODES = {"D": (0, 0), "A": (10, 0), "B": (10, 1), "C": (-10, 0)}
NET = RoadNetwork(NODES, [Road("D", "A", 10, "asphalt"), Road("A", "B", 1, "asphalt"), Road("D", "C", 10, "asphalt"),
                          Road("D", "B", 5, "earth", rainy_passable=False)])
TRUCK = Vehicle("t", 10, 1.0, 0.0)


def test_rough_road_cost_factor_and_rain_closure():
    dry, phys = shortest_paths(NET, "D", "dry")
    wet, _ = shortest_paths(NET, "D", "rainy")
    assert abs(dry["B"] - 8.5) < 1e-9 and phys["B"] == 5          # earth road 5 km x 1.7 beats asphalt 11 km
    assert abs(wet["B"] - 11) < 1e-9                               # closed in the rains: detour via A


def test_unknown_node_raises():
    try:
        shortest_paths(NET, "X")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_savings_merges_neighbours_not_opposites():
    routes = savings_routes(NET, "D", [PickupRequest("A", 4), PickupRequest("B", 4), PickupRequest("C", 4)], TRUCK)
    stops = sorted(tuple(sorted(r.stops)) for r in routes)
    assert stops == [("A", "B"), ("C",)]


def test_capacity_respected_and_full_trucks_split():
    routes = savings_routes(NET, "D", [PickupRequest("A", 23), PickupRequest("B", 4)], TRUCK)
    assert all(r.load_t <= 10 + 1e-9 for r in routes)
    assert abs(sum(r.load_t for r in routes) - 27) < 1e-9 and sum(r.load_t == 10 for r in routes) == 2


def test_unreachable_node_raises():
    net = RoadNetwork({"D": (0, 0), "Z": (5, 5)}, [Road("D", "Z", 5, "earth", rainy_passable=False)])
    try:
        savings_routes(net, "D", [PickupRequest("Z", 3)], TRUCK, "rainy")
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError")


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

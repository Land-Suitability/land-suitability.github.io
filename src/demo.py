#!/usr/bin/env python3
"""
Stage 11 demo on a SYNTHETIC road network (no real roads or places).

A collection centre (CC), a market town (TOWN) on an asphalt road, 12 kebeles on gravel and earth roads.
  1. Cost of reaching each kebele in the dry and rainy seasons (some earth roads close in the rains)
  2. Pickups to the centre: one truck per kebele versus Clarke-Wright consolidated routes
  3. Transport cost per tonne by kebele, dry versus rainy
Writes assets/demo-logistics.json for the charts.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from logistics import PickupRequest, Road, RoadNetwork, Vehicle, savings_routes, shortest_paths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

NODES = {"CC": (0, 0), "TOWN": (35, 0), "J1": (8, 6), "J2": (8, -6), "J3": (-8, 4),
         **{f"K{i:02d}": xy for i, xy in enumerate([(12, 12), (16, 8), (14, -10), (18, -14), (4, 14), (-6, 12),
                                                     (-14, 8), (-12, -4), (-4, -12), (6, -16), (22, 4), (20, 16)], 1)}}
ROADS = [
    Road("CC", "TOWN", 36, "asphalt"), Road("CC", "J1", 10, "gravel"), Road("CC", "J2", 10, "gravel"), Road("CC", "J3", 9, "gravel"),
    Road("J1", "K01", 8, "earth", False), Road("J1", "K02", 9, "gravel"), Road("K01", "K12", 9, "earth", False),
    Road("K02", "K11", 7, "gravel"), Road("K11", "K12", 13, "gravel"), Road("J1", "K05", 9, "earth", False),
    Road("K05", "K06", 10, "earth"), Road("J3", "K06", 9, "gravel"), Road("J3", "K07", 8, "earth", False),
    Road("J3", "K08", 9, "gravel"), Road("K07", "K08", 12, "gravel"), Road("J2", "K03", 8, "gravel"),
    Road("K03", "K04", 6, "earth", False), Road("J2", "K10", 11, "earth"), Road("K10", "K09", 11, "gravel"),
    Road("K09", "K08", 10, "earth"), Road("K04", "K10", 13, "gravel"), Road("K01", "K05", 9, "gravel"),
    Road("TOWN", "K11", 15, "gravel"),
]
TONNES = {"K01": 28, "K02": 14, "K03": 22, "K04": 9, "K05": 12, "K06": 7, "K07": 18, "K08": 11, "K09": 6, "K10": 15, "K11": 24, "K12": 10}
TRUCK = Vehicle("10 t truck", 10, cost_per_km=45, fixed_per_trip=1500)


def main() -> int:
    try:
        net = RoadNetwork(NODES, ROADS)
        kebeles = sorted(TONNES)
        print("== 1. Cost-weighted km from the centre (dry / rainy)")
        dry, _ = shortest_paths(net, "CC", "dry")
        wet, _ = shortest_paths(net, "CC", "rainy")
        for k in kebeles:
            extra = wet[k] / dry[k] - 1
            print(f"  {k}: {dry[k]:6.1f} / {wet[k]:6.1f}  {'+' + format(extra, '.0%') + ' detour' if extra > 0.001 else ''}")

        pickups = [PickupRequest(k, TONNES[k]) for k in kebeles]
        total_t = sum(TONNES.values())
        res = {}
        print("\n== 2. Collecting", total_t, "t to the centre")
        for season in ("dry", "rainy"):
            D = shortest_paths(net, "CC", season)[0]
            naive_trips = sum(-(-TONNES[k] // TRUCK.capacity_t) for k in kebeles)
            # naive: every load goes as its own round trip, partially filled trucks included
            naive_cost = sum((-(-TONNES[k] // TRUCK.capacity_t)) * (TRUCK.fixed_per_trip + 2 * D[k] * TRUCK.cost_per_km) for k in kebeles)
            routes = savings_routes(net, "CC", pickups, TRUCK, season)
            cost = sum(r.cost_birr for r in routes)
            res[season] = {"naive_trips": int(naive_trips), "naive_cost": round(naive_cost), "routes": len(routes),
                           "cost": round(cost), "km": round(sum(r.km for r in routes), 1)}
            print(f"  {season:5s}: one truck per load {int(naive_trips)} trips, {naive_cost:,.0f} birr | savings routes "
                  f"{len(routes)} trips, {cost:,.0f} birr ({cost / naive_cost - 1:+.0%}), {cost / total_t:,.0f} birr/t")
            for r in routes:
                if len(r.stops) > 1:
                    print(f"    [DEBUG] shared route {' -> '.join(r.stops)}: {r.load_t:.0f} t, {r.km:.0f} cost-km, {r.cost_per_t:,.0f} birr/t")

        per_t = {}
        for season in ("dry", "rainy"):
            D = shortest_paths(net, "CC", season)[0]
            per_t[season] = [round((TRUCK.fixed_per_trip + 2 * D[k] * TRUCK.cost_per_km) / TRUCK.capacity_t) for k in kebeles]
        out = {"kebeles": kebeles, "per_t": per_t, "summary": res, "tonnes": TONNES,
               "closed_roads": [f"{r.a}-{r.b}" for r in ROADS if not r.rainy_passable]}
        path = ROOT / "assets" / "demo-logistics.json"
        path.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"  [DEBUG] wrote {path.relative_to(ROOT)}")
        return 0
    except (KeyError, ValueError, RuntimeError) as e:
        print(f"[DATA ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

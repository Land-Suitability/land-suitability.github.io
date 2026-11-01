"""
Routing on the rural road network.

  shortest_paths      Dijkstra on cost-weighted km (rough roads cost more); season "dry" or "rainy"
  savings_routes      Clarke-Wright savings heuristic for collecting pickups into a depot with capacity limits:
                        start with one trip per stop, then merge the two trips whose merge saves the most
                        distance (d(depot,i) + d(depot,j) - d(i,j)) while the truck still has room
  route_cost          distance and cost of a closed trip depot -> stops -> depot
Pickups larger than a truck are first split into full-truck trips.
"""
from __future__ import annotations

import heapq

from .domain import PickupRequest, RoadNetwork, Route, Vehicle


def shortest_paths(net: RoadNetwork, source: str, season: str = "dry") -> tuple[dict[str, float], dict[str, float]]:
    """Returns (cost-weighted km, physical km) from source to every reachable node."""
    if source not in net.nodes:
        raise KeyError(f"Unknown node {source}")
    adj = net.neighbours(season)
    best = {source: 0.0}
    phys = {source: 0.0}
    pq = [(0.0, 0.0, source)]
    while pq:
        c, k, u = heapq.heappop(pq)
        if c > best.get(u, float("inf")):
            continue
        for v, r in adj[u]:
            nc = c + r.km * r.cost_factor()
            if nc < best.get(v, float("inf")):
                best[v], phys[v] = nc, k + r.km
                heapq.heappush(pq, (nc, k + r.km, v))
    return best, phys


def _matrix(net: RoadNetwork, nodes: list[str], season: str) -> dict[tuple[str, str], float]:
    m = {}
    for a in nodes:
        dist, _ = shortest_paths(net, a, season)
        for b in nodes:
            if b not in dist:
                raise RuntimeError(f"{b} is unreachable from {a} in the {season} season")
            m[(a, b)] = dist[b]
    return m


def route_cost(stops: list[str], depot: str, D: dict, veh: Vehicle, load: float) -> Route:
    path = [depot] + stops + [depot]
    km = sum(D[(path[i], path[i + 1])] for i in range(len(path) - 1))
    return Route(veh.vehicle_type, tuple(stops), load, km, veh.fixed_per_trip + km * veh.cost_per_km)


def savings_routes(net: RoadNetwork, depot: str, pickups: list[PickupRequest], veh: Vehicle,
                   season: str = "dry") -> list[Route]:
    if veh.capacity_t <= 0:
        raise ValueError("Vehicle capacity must be positive")
    routes_out: list[Route] = []
    rest: dict[str, float] = {}
    for p in pickups:                                    # full-truck trips first
        full, rem = divmod(p.tonnes, veh.capacity_t)
        rest[p.node] = rest.get(p.node, 0.0) + rem
        for _ in range(int(full)):
            routes_out.append(("FULL", p.node, veh.capacity_t))
    nodes = [depot] + sorted(set(p.node for p in pickups))
    D = _matrix(net, nodes, season)
    full_routes = [route_cost([n], depot, D, veh, t) for _, n, t in routes_out]
    stops = [n for n, t in rest.items() if t > 1e-9]
    routes = {n: [n] for n in stops}
    load = {n: rest[n] for n in stops}
    owner = {n: n for n in stops}
    sav = sorted(((D[(depot, i)] + D[(depot, j)] - D[(i, j)], i, j) for i in stops for j in stops if i < j), reverse=True)
    for s, i, j in sav:
        ri, rj = owner[i], owner[j]
        if ri == rj or s <= 0 or load[ri] + load[rj] > veh.capacity_t + 1e-9:
            continue
        a, b = routes[ri], routes[rj]
        # merge only at route ends (i and j must be endpoints)
        if a[-1] == i and b[0] == j:
            new = a + b
        elif a[0] == i and b[-1] == j:
            new = b + a
        elif a[0] == i and b[0] == j:
            new = a[::-1] + b
        elif a[-1] == i and b[-1] == j:
            new = a + b[::-1]
        else:
            continue
        routes[ri] = new
        load[ri] += load[rj]
        for n in b:
            owner[n] = ri
        del routes[rj], load[rj]
    return full_routes + [route_cost(r, depot, D, veh, load[k]) for k, r in routes.items()]

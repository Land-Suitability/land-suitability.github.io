"""
Domain model for Stage 11: Logistics & Transportation.

Ubiquitous language
-------------------
RoadNetwork     Nodes (kebeles, centres, towns) and road segments with length, surface and whether the segment
                is passable in the rainy season (earth roads often are not).
Vehicle         A truck type: capacity (t), cost per km, fixed cost per trip.
PickupRequest   Tonnes waiting at a node to be moved to a centre (from stages 09 and 10), with a ready date.
Route           One vehicle trip: depot -> stops -> depot, with distance, load and cost.
Shipment        Lots on a route with departure and expected arrival (traceable to stage 09 lots).

Analogy
-------
A school bus that collects children from many villages. Sending one bus per child is easy to plan but
wasteful; one bus doing a well-chosen loop fills its seats and drives far less. In the rains, some village
tracks flood, so the bus needs a different loop, and it is better to know that before the rains start.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Road:
    a: str
    b: str
    km: float
    surface: str                 # "asphalt" | "gravel" | "earth"
    rainy_passable: bool = True

    def cost_factor(self) -> float:
        """Rough-road penalty on cost per km (fuel, wear, time)."""
        return {"asphalt": 1.0, "gravel": 1.3, "earth": 1.7}[self.surface]


@dataclass
class RoadNetwork:
    nodes: dict[str, tuple[float, float]]
    roads: list[Road] = field(default_factory=list)

    def neighbours(self, season: str):
        adj: dict[str, list[tuple[str, Road]]] = {n: [] for n in self.nodes}
        for r in self.roads:
            if season == "rainy" and not r.rainy_passable:
                continue
            if r.a not in adj or r.b not in adj:
                raise KeyError(f"Road {r.a}-{r.b} references an unknown node")
            adj[r.a].append((r.b, r))
            adj[r.b].append((r.a, r))
        return adj


@dataclass(frozen=True)
class Vehicle:
    vehicle_type: str
    capacity_t: float
    cost_per_km: float           # birr per km on asphalt, loaded or empty
    fixed_per_trip: float        # driver day, loading


@dataclass(frozen=True)
class PickupRequest:
    node: str
    tonnes: float
    lot_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Route:
    vehicle_type: str
    stops: tuple[str, ...]
    load_t: float
    km: float
    cost_birr: float

    @property
    def cost_per_t(self) -> float:
        return self.cost_birr / self.load_t if self.load_t else float("inf")

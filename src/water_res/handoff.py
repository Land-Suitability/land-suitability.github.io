"""
Reading the hand-off from Phase 1 module 1 (land availability, stage 01).

Stage branches never import each other's code; modules exchange versioned data files. This loader
checks the contract before anything uses it, so a changed or truncated file fails loudly here, not
as a strange map later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CONTRACT = "aiae.phase1.available_land"
SUPPORTED = {"0.1"}
REQUIRED = ("status", "cover", "altitude_m", "slope_pct", "rain_season_mm", "soil_depth_cm", "drainage_class", "road_km")


@dataclass(frozen=True)
class AvailableLandGrid:
    """Module 1's output as module 2 sees it: grids on one co-registered raster."""
    layers: dict[str, np.ndarray]
    cell_m: float
    status_codes: dict[str, int]
    cover_codes: dict[str, int]
    provenance: dict

    @property
    def shape(self) -> tuple[int, int]:
        return self.layers["status"].shape

    @property
    def cell_ha(self) -> float:
        return self.cell_m ** 2 / 10_000

    def available_mask(self) -> np.ndarray:
        """Land a plan may count on now: in use or expandable (module 1's definition)."""
        s = self.layers["status"]
        return (s == self.status_codes["IN_USE"]) | (s == self.status_codes["EXPANDABLE"])

    def cover_is(self, *names: str) -> np.ndarray:
        return np.isin(self.layers["cover"], [self.cover_codes[n] for n in names])


def load_handoff(path: Path) -> AvailableLandGrid:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"module 1 hand-off not found at {path}; copy it from stage/01-land-intelligence "
                                "assets/handoff-available-land.json") from None
    if d.get("contract") != CONTRACT:
        raise ValueError(f"expected contract {CONTRACT!r}, got {d.get('contract')!r}")
    if d.get("version") not in SUPPORTED:
        raise ValueError(f"hand-off version {d.get('version')!r} not supported; supported: {sorted(SUPPORTED)}")
    missing = [k for k in REQUIRED if k not in d.get("layers", {})]
    if missing:
        raise KeyError(f"hand-off is missing layers {missing}")
    rows, cols = d["grid"]["rows"], d["grid"]["cols"]
    layers = {}
    for k in REQUIRED:
        a = np.asarray(d["layers"][k], dtype=float)
        if a.shape != (rows, cols):
            raise ValueError(f"layer {k} has shape {a.shape}, expected {(rows, cols)}")
        if np.isnan(a).any():
            raise ValueError(f"layer {k} has missing values")
        layers[k] = a
    for k in ("status", "cover"):
        layers[k] = layers[k].astype(int)
    return AvailableLandGrid(layers, float(d["grid"]["cell_m"]), d["codes"]["status"], d["codes"]["cover"], d.get("provenance", {}))

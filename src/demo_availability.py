#!/usr/bin/env python3
"""
Land availability demo on the SAME synthetic 16 km landscape as src/demo.py (no real data).

  1. Build synthetic land cover, protected church forests, communal grazing and a road.
  2. Classify availability: in use, expandable, conditional, excluded (with reasons).
  3. Combine with suitability: hectares that are both available and S1/S2, per crop.
  4. Write assets/availability-maps.svg and assets/demo-availability.json for the page.

Run from the branch root:  python3 src/demo_availability.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo import synthetic_landscape  # noqa: E402
from land_intel import (AvailabilityRules, AvailabilityStatus, AvailableLand, LandCover, Method, Reason,  # noqa: E402
                        assess_availability, assess_grid, available_and_suitable)
from land_intel.availability import REASON_TEXT  # noqa: E402
from land_intel.factors import PROFILES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
N = 64
COVER_COL = {LandCover.CROPLAND: "#e9c46a", LandCover.GRASSLAND: "#a7c957", LandCover.SHRUBLAND: "#6a994e",
             LandCover.FOREST: "#2d6a4f", LandCover.WATER: "#5aa0c8", LandCover.WETLAND: "#94c5cc",
             LandCover.BUILT_UP: "#9a4a28", LandCover.BARE: "#c9bfae"}
STATUS_COL = {AvailabilityStatus.IN_USE: "#3f6b34", AvailabilityStatus.EXPANDABLE: "#8cc37a",
              AvailabilityStatus.CONDITIONAL: "#e3a64b", AvailabilityStatus.EXCLUDED: "#c9c3b6"}


def synthetic_cover(layers: dict[str, np.ndarray], seed: int = 11) -> dict[str, np.ndarray]:
    """Plausible highland land cover: cropland on gentle land, forest on the escarpment, a lake and river, a town."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N] / (N - 1)
    slope = layers["slope_pct"]
    noise = sum(a * np.sin(f * np.pi * xx + p) * np.cos(g * np.pi * yy + q)
                for a, f, g, p, q in rng.uniform([0.3, 2, 2, 0, 0], [1, 7, 7, 3, 3], (5, 5)))
    cover = np.full((N, N), int(LandCover.CROPLAND))
    cover[(noise > 0.6) & (slope < 25)] = LandCover.GRASSLAND
    cover[(slope > 18) & (noise > 0.2)] = LandCover.SHRUBLAND
    cover[(slope > 26) | ((xx > 0.86) & (noise > -0.3))] = LandCover.FOREST          # escarpment woodland
    cover[(slope > 40) & (noise < -0.8)] = LandCover.BARE
    lake = (xx - 0.14) ** 2 / 0.010 + (yy - 0.84) ** 2 / 0.006 < 1
    wet = ((xx - 0.14) ** 2 / 0.016 + (yy - 0.84) ** 2 / 0.011 < 1) & ~lake
    cover[wet] = LandCover.WETLAND
    t = np.linspace(0, 1, 400)                                                           # river NE -> lake
    rx, ry = 0.95 - 0.78 * t, 0.08 + 0.72 * t + 0.06 * np.sin(6 * t)
    for x, y in zip(rx, ry):
        cover[min(N - 1, int(y * (N - 1))), min(N - 1, int(x * (N - 1)))] = LandCover.WATER
    cover[lake] = LandCover.WATER
    town = (xx - 0.52) ** 2 + (yy - 0.46) ** 2 < 0.0025
    villages = [(0.30, 0.25), (0.70, 0.72), (0.28, 0.62)]
    for vx, vy in villages:
        town |= (xx - vx) ** 2 + (yy - vy) ** 2 < 0.0004
    cover[town] = LandCover.BUILT_UP
    # church forests: small protected groves beside the settlements (a well-known Amhara landscape feature)
    protected = np.zeros((N, N), bool)
    for vx, vy in [(0.34, 0.22), (0.66, 0.76), (0.56, 0.42), (0.24, 0.66)]:
        grove = (xx - vx) ** 2 + (yy - vy) ** 2 < 0.0006
        protected |= grove
        cover[grove & (cover != LandCover.BUILT_UP)] = LandCover.FOREST
    # communal grazing: open land in the poorly drained valley and around villages
    near_village = np.zeros((N, N), bool)
    for vx, vy in villages:
        near_village |= (xx - vx) ** 2 + (yy - vy) ** 2 < 0.012
    valley = (layers["drainage_class"] < 2.6)
    grazing = (valley | near_village) & np.isin(cover, [LandCover.GRASSLAND, LandCover.SHRUBLAND])
    # one gravel road west -> town -> east; distance in km on 250 m cells
    road = np.zeros((N, N), bool)
    road_line = [(x, 0.52 - 0.14 * x + 0.06 * np.sin(5 * x)) for x in np.linspace(0, 1, 300)]
    for x, y in road_line:
        road[int(y * (N - 1)), int(x * (N - 1))] = True
    ri, rj = np.nonzero(road)
    ii, jj = np.mgrid[0:N, 0:N]
    d = np.sqrt((ii[..., None] - ri) ** 2 + (jj[..., None] - rj) ** 2).min(axis=2)
    return {"cover": cover, "protected": protected, "grazing": grazing, "road": road, "road_line": road_line, "road_km": d * 0.25}


def raster(values: np.ndarray, colours: dict, x0: int, y0: int, cell: int) -> list[str]:
    out = []
    for i in range(N):                               # run-length encode rows to keep the SVG small
        j = 0
        while j < N:
            v = int(values[i, j]); j0 = j
            while j < N and int(values[i, j]) == v:
                j += 1
            out.append(f'<rect x="{x0 + j0 * cell}" y="{y0 + i * cell}" width="{(j - j0) * cell}" height="{cell}" fill="{colours[v]}"/>')
    return out


def maps_svg(cover, status, plannable, road_line, path: Path, cell: int = 4) -> None:
    pad, gap, top, size = 12, 26, 34, N * cell
    w, h = pad * 2 + 3 * size + 2 * gap, top + size + 112
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Helvetica, Arial, sans-serif" role="img" '
         f'aria-label="Three synthetic maps: land cover, land availability, and teff land that is both available and suitable." shape-rendering="crispEdges">',
         f'<rect width="{w}" height="{h}" fill="#fbfaf6"/>']
    plan_col = {0: "#e4ded1", 1: "#cfe3c4", 2: "#1a9641"}
    panels = [("1. Land cover today", cover, COVER_COL), ("2. Availability", status, STATUS_COL), ("3. Teff: available and S1 or S2", plannable, plan_col)]
    for k, (title, vals, cols) in enumerate(panels):
        x0 = pad + k * (size + gap)
        p.append(f'<text x="{x0}" y="22" font-size="13.5" font-weight="bold" fill="#1f2a20">{title}</text>')
        p += raster(vals, {int(a): b for a, b in cols.items()}, x0, top, cell)
        d = "M" + " L".join(f"{x0 + (x * (N - 1) + 0.5) * cell:.1f},{top + (y * (N - 1) + 0.5) * cell:.1f}" for x, y in road_line[::6] + road_line[-1:])
        p.append(f'<path d="{d}" fill="none" stroke="#fbfaf6" stroke-width="4" shape-rendering="geometricPrecision"/>'
                 f'<path d="{d}" fill="none" stroke="#4a4a4a" stroke-width="2" shape-rendering="geometricPrecision"/>')
        p.append(f'<rect x="{x0}" y="{top}" width="{size}" height="{size}" fill="none" stroke="#b9b2a2"/>')
    legends = [
        [("cropland", COVER_COL[LandCover.CROPLAND]), ("grassland", COVER_COL[LandCover.GRASSLAND]), ("shrubland", COVER_COL[LandCover.SHRUBLAND]),
         ("forest", COVER_COL[LandCover.FOREST]), ("water", COVER_COL[LandCover.WATER]), ("wetland", COVER_COL[LandCover.WETLAND]),
         ("built-up", COVER_COL[LandCover.BUILT_UP]), ("bare", COVER_COL[LandCover.BARE])],
        [("in use", STATUS_COL[AvailabilityStatus.IN_USE]), ("expandable", STATUS_COL[AvailabilityStatus.EXPANDABLE]),
         ("conditional", STATUS_COL[AvailabilityStatus.CONDITIONAL]), ("excluded", STATUS_COL[AvailabilityStatus.EXCLUDED])],
        [("available and S1/S2", plan_col[2]), ("available, S3 or N", plan_col[1]), ("not available", plan_col[0])],
    ]
    for k, items in enumerate(legends):
        x0 = pad + k * (size + gap)
        for idx, (lab, col) in enumerate(items):
            per_row = 1 if k == 2 else 2                     # long labels in the last legend get a line each
            lx, ly = x0 + (idx % per_row) * (size // 2), top + size + 20 + (idx // per_row) * 18
            p.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="2" fill="{col}"/><text x="{lx + 17}" y="{ly}" font-size="12" fill="#1f2a20">{lab}</text>')
    p.append(f'<text x="{w - pad}" y="{h - 10}" font-size="11" text-anchor="end" fill="#666">synthetic 16 km landscape, 250 m cells; dark line: road; v0.1</text>')
    p.append("</svg>")
    path.write_text("\n".join(p), encoding="utf-8")


def write_handoff(layers, lc, av, rules, path: Path) -> None:
    """
    Module 1 -> module 2 hand-off (Phase 1): the grids the next module needs, in one versioned file.
    Stage branches cannot import each other's code, so modules exchange data, never code.
    """
    def grid(a, dp=0):
        return [[round(float(v), dp) if dp else int(round(float(v))) for v in row] for row in np.asarray(a)]
    handoff = {
        "contract": "aiae.phase1.available_land", "version": "0.1", "producer": "stage/01-land-intelligence src/demo_availability.py",
        "note": "Synthetic 16 km landscape; no real land. Rows run north to south, columns west to east.",
        "grid": {"rows": N, "cols": N, "cell_m": rules.cell_size_m},
        "codes": {"status": {s.name: int(s) for s in AvailabilityStatus}, "cover": {c.name: int(c) for c in LandCover}},
        "layers": {
            "status": grid(av.status), "cover": grid(lc["cover"]),
            "altitude_m": grid(layers["altitude_m"]), "slope_pct": grid(layers["slope_pct"], 1),
            "rain_season_mm": grid(layers["rain_season_mm"]), "soil_depth_cm": grid(layers["soil_depth_cm"]),
            "drainage_class": grid(layers["drainage_class"], 1), "road_km": grid(lc["road_km"], 2),
        },
    }
    path.write_text(json.dumps(handoff, separators=(",", ":")), encoding="utf-8")
    print(f"  [DEBUG] wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB, contract {handoff['contract']} v{handoff['version']})")


def main() -> int:
    try:
        layers = synthetic_landscape()
        lc = synthetic_cover(layers)
        rules = AvailabilityRules(cell_size_m=250)
        av = assess_availability(lc["cover"], layers["slope_pct"], lc["protected"], lc["grazing"], lc["road_km"], rules)
        total = N * N * rules.cell_ha
        ha = av.hectares()
        print("== Land availability (synthetic 16 km landscape) ==")
        for s in reversed(list(AvailabilityStatus)):
            print(f"  {s.name:12s} {ha[s.name]:8,.0f} ha  {ha[s.name] / total:6.1%}")
        reasons = {k: v for k, v in av.reason_hectares().items() if v > 0}
        print("  reasons (ha, a cell can carry several):", ", ".join(f"{k} {v:,.0f}" for k, v in sorted(reasons.items(), key=lambda x: -x[1])))

        print("\n== Available AND suitable (AHP weighted, in use + expandable) ==")
        summary = AvailableLand("DEMO-CLUSTER", ha)
        naive = {}
        teff_rank = None
        for crop, profile in PROFILES.items():
            rank = assess_grid(layers, profile, Method.AHP_WLC)["rank"]
            if crop == "teff":
                teff_rank = rank
            summary.suitable_available_ha[crop] = available_and_suitable(av, rank)
            naive[crop] = float(((rank >= 2).sum()) * rules.cell_ha)
            plan = summary.plannable_ha(crop)
            print(f"  {crop:12s} suitable anywhere (S1+S2) {naive[crop]:8,.0f} ha | also available {plan:8,.0f} ha "
                  f"({plan / naive[crop]:.0%} of the suitable land)")

        ok = np.isin(av.status, [AvailabilityStatus.IN_USE, AvailabilityStatus.EXPANDABLE])
        plannable = np.where(ok & (teff_rank >= 2), 2, np.where(ok, 1, 0))
        maps_svg(lc["cover"], av.status, plannable, lc["road_line"], ROOT / "assets" / "availability-maps.svg")
        i, j = np.argwhere(av.status == AvailabilityStatus.CONDITIONAL)[0]
        print(f"\n  [DEBUG] example conditional cell ({i},{j}): {av.explain(i, j)}")

        out = {"note": "Synthetic 16 km landscape; indicative rules v0.1. Not real land.",
               "total_ha": total, "hectares_by_status": ha, "reason_hectares": reasons,
               "suitable_anywhere_ha": naive, "available_and_suitable_ha": summary.suitable_available_ha,
               "rules": {"max_slope_pct": rules.max_slope_pct, "terrace_slope_pct": rules.terrace_slope_pct,
                         "water_buffer_m": rules.water_buffer_m, "remote_road_km": rules.remote_road_km}}
        (ROOT / "assets" / "demo-availability.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        write_handoff(layers, lc, av, rules, ROOT / "assets" / "handoff-available-land.json")
        print("  [DEBUG] wrote assets/availability-maps.svg and assets/demo-availability.json")
        return 0
    except (KeyError, ValueError) as e:
        print(f"[DATA ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

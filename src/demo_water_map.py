#!/usr/bin/env python3
"""
Water availability mapping demo (Phase 1, module 2) on the SYNTHETIC landscape from module 1.

  1. Read module 1's hand-off (data/handoff-module1.json): available land and terrain.
  2. Streams from the terrain (fill, D8, accumulation) and their monthly flow; sustainable share.
  3. Groundwater potential from six weighted factors; springs at the foot of steep slopes.
  4. Water access for every available cell: gravity, pumped, groundwater or harvest only.
  5. How many hectares each source can irrigate in its leanest month (wheat demand from stage 02).
  6. Write assets/water-maps.svg and assets/demo-water-availability.json for the page.

Run from the branch root:  python3 src/demo_water_map.py
No real river, well or farmer data is used.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from water_res import (MONTHS, AccessClass, Confidence, Geology, GwClass, MappingRules, WaterPoint,  # noqa: E402
                       build_budget, d8_receivers, fill_depressions, flow_accumulation, groundwater_potential,
                       load_handoff, stream_flow_m3, water_access)
from demo import PLANS, RAIN, TMAX, TMIN, make_cluster  # noqa: E402  (stage 02 budget inputs)

ROOT = Path(__file__).resolve().parent.parent
# specific runoff (mm per month) for a highland catchment: Kiremt flood, Bega recession (~290 mm a year)
RUNOFF_MM = (4.0, 3.0, 2.6, 3.0, 5.0, 12.0, 55.0, 80.0, 60.0, 35.0, 15.0, 8.0)
SECONDS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]) * 86400.0
GW_COL = {1: "#eaf1f8", 2: "#c3d8ee", 3: "#89b3dc", 4: "#4a86c5", 5: "#1f5a99"}
ACC_COL = {AccessClass.NOT_ASSESSED: "#ebe6db", AccessClass.HARVEST_ONLY: "#e3a64b", AccessClass.GROUNDWATER: "#5bb3a9",
           AccessClass.PUMPED: "#4a86c5", AccessClass.GRAVITY: "#1f4e8c"}


def factor_layers(g, upstream_km2, stream, rng) -> dict:
    """Synthetic geology and lineaments, then every groundwater factor scored 0..1."""
    n, m = g.shape
    alt, slope = g.layers["altitude_m"], g.layers["slope_pct"]
    jj = np.mgrid[0:n, 0:m][1] / (m - 1)
    geology = np.full((n, m), int(Geology.FRACTURED_BASALT))
    geology[(slope > 20) & (jj > 0.72)] = Geology.MASSIVE_BASALT
    wet = g.cover_is("WATER", "WETLAND")
    near_wet = np.zeros_like(wet)
    for di in range(-3, 4):
        for dj in range(-3, 4):
            near_wet |= np.roll(np.roll(wet, di, 0), dj, 1)
    geology[(alt < np.percentile(alt, 18)) | near_wet | (g.layers["drainage_class"] < 2.6)] = Geology.ALLUVIUM
    # lineaments (fracture zones): a few straight lines; score by distance
    ii2, jj2 = np.mgrid[0:n, 0:m]
    dmin = np.full((n, m), np.inf)
    for _ in range(4):
        i0, j0, ang = rng.uniform(0, n), rng.uniform(0, m), rng.uniform(0, np.pi)
        dmin = np.minimum(dmin, np.abs((ii2 - i0) * np.cos(ang) - (jj2 - j0) * np.sin(ang)))
    dist_m = dmin * g.cell_m
    lineaments = np.where(dist_m < 500, 1.0, np.where(dist_m < 1000, 0.6, 0.2))
    slope_s = np.select([slope < 5, slope < 15, slope < 30], [1.0, 0.6, 0.3], 0.1)
    rain = g.layers["rain_season_mm"]
    rain_s = (rain - rain.min()) / (np.ptp(rain) or 1)
    dens = np.zeros((n, m))
    for di in range(-4, 5):
        for dj in range(-4, 5):
            dens += np.roll(np.roll(stream.astype(float), di, 0), dj, 1)
    dens_s = 1 - dens / (dens.max() or 1)
    geo_s = np.select([geology == Geology.ALLUVIUM, geology == Geology.FRACTURED_BASALT], [1.0, 0.55], 0.15)
    soil_s = np.clip(g.layers["drainage_class"] / 5, 0, 1)
    return {"geology_code": geology, "lineament_dist_m": dist_m,
            "factors": {"geology": geo_s, "lineaments": lineaments, "slope": slope_s, "rainfall": rain_s,
                        "stream_density": dens_s, "soil_drainage": soil_s}}


def find_springs(g, gw_idx, gw_cls, stream, k=6, spacing=6) -> list[tuple[int, int]]:
    """Spring candidates: gentle cell, steep ground within 2 cells, moderate or better groundwater, not a stream."""
    slope = g.layers["slope_pct"]
    n, m = slope.shape
    steep_near = np.zeros_like(slope)
    for di in range(-2, 3):
        for dj in range(-2, 3):
            steep_near = np.maximum(steep_near, np.roll(np.roll(slope, di, 0), dj, 1))
    cand = (slope < 15) & (steep_near >= 22) & (gw_cls >= GwClass.MODERATE) & ~stream & ~g.cover_is("WATER", "WETLAND")
    cand[:2, :] = cand[-2:, :] = cand[:, :2] = cand[:, -2:] = False
    picks = []
    for flat in np.argsort(np.where(cand, gw_idx, -1).ravel())[::-1]:
        i, j = divmod(int(flat), m)
        if not cand[i, j] or len(picks) >= k:
            break
        if all(max(abs(i - a), abs(j - b)) >= spacing for a, b in picks):
            picks.append((i, j))
    return picks


def raster(vals, cols, x0, y0, cell, n):
    out = []
    for i in range(n):
        j = 0
        while j < n:
            v = int(vals[i, j]); j0 = j
            while j < n and int(vals[i, j]) == v:
                j += 1
            out.append(f'<rect x="{x0 + j0 * cell}" y="{y0 + i * cell}" width="{(j - j0) * cell}" height="{cell}" fill="{cols[v]}"/>')
    return out


def maps_svg(g, stream, rec, upstream_km2, springs, gw_cls, wam, path: Path, cell: int = 4) -> None:
    n = g.shape[0]
    pad, gap, top, size = 12, 26, 34, n * cell
    w, h = pad * 2 + 3 * size + 2 * gap, top + size + 112
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Helvetica, Arial, sans-serif" role="img" shape-rendering="crispEdges" '
         f'aria-label="Three synthetic maps: streams and springs over the terrain, groundwater potential, and water access for available land.">',
         f'<rect width="{w}" height="{h}" fill="#fbfaf6"/>']
    alt = g.layers["altitude_m"]
    shade = np.digitize(alt, np.percentile(alt, [20, 40, 60, 80]))
    terrain = {0: "#e9efe0", 1: "#dfe8d3", 2: "#d3dfc4", 3: "#c6d4b4", 4: "#b8c8a3", 9: "#9fc9e3"}
    # background water: the lake and its wetland only (wide water bodies); streams come from the terrain analysis
    wet = g.cover_is("WATER", "WETLAND").astype(int)
    nb = sum(np.roll(np.roll(wet, di, 0), dj, 1) for di in (-1, 0, 1) for dj in (-1, 0, 1))
    lake = wet.astype(bool) & (nb >= 7)
    base = np.where(lake, 9, shade)
    panels = [("1. Streams and springs", base, terrain), ("2. Groundwater potential", gw_cls, GW_COL),
              ("3. Water access for available land", wam.access, {int(k): v for k, v in ACC_COL.items()})]
    for k, (title, vals, cols) in enumerate(panels):
        x0 = pad + k * (size + gap)
        p.append(f'<text x="{x0}" y="22" font-size="13.5" font-weight="bold" fill="#1f2a20">{title}</text>')
        p += raster(vals, cols, x0, top, cell, n)
        if k in (0, 2):                                    # streams on the terrain and on the access map
            segs = []
            for flat in np.flatnonzero(stream.ravel()):
                r = rec[flat]
                if r < 0:
                    continue
                i, j = divmod(int(flat), n); a, b = divmod(int(r), n)
                wdt = 0.8 + 1.1 * np.log10(max(upstream_km2[i, j], 1))
                segs.append(f'<line x1="{x0 + (j + .5) * cell}" y1="{top + (i + .5) * cell}" x2="{x0 + (b + .5) * cell}" y2="{top + (a + .5) * cell}" stroke-width="{wdt:.1f}"/>')
            p.append(f'<g stroke="{"#2a78d6" if k == 0 else "#0e2f57"}" stroke-linecap="round" shape-rendering="geometricPrecision">' + "".join(segs) + "</g>")
        if k == 0:
            for i, j in springs:
                p.append(f'<circle cx="{x0 + (j + .5) * cell}" cy="{top + (i + .5) * cell}" r="5" fill="#fff" stroke="#2a78d6" stroke-width="2.5" shape-rendering="geometricPrecision"/>')
        p.append(f'<rect x="{x0}" y="{top}" width="{size}" height="{size}" fill="none" stroke="#b9b2a2"/>')
    legends = [[("stream (width: catchment size)", "#2a78d6"), ("spring", "#ffffff"), ("lake and wetland", "#9fc9e3")],
               [("very low", GW_COL[1]), ("low", GW_COL[2]), ("moderate", GW_COL[3]), ("high", GW_COL[4]), ("very high", GW_COL[5])],
               [("gravity canal", ACC_COL[AccessClass.GRAVITY]), ("pumped lift", ACC_COL[AccessClass.PUMPED]),
                ("shallow wells", ACC_COL[AccessClass.GROUNDWATER]), ("harvest only", ACC_COL[AccessClass.HARVEST_ONLY]),
                ("not available (module 1)", ACC_COL[AccessClass.NOT_ASSESSED])]]
    for k, items in enumerate(legends):
        x0 = pad + k * (size + gap)
        per_row = 1 if k == 0 else 2
        for idx, (lab, col) in enumerate(items):
            lx, ly = x0 + (idx % per_row) * (size // 2), top + size + 20 + (idx // per_row) * 18
            stroke = ' stroke="#2a78d6" stroke-width="2"' if col == "#ffffff" else ""
            p.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="2" fill="{col}"{stroke}/><text x="{lx + 17}" y="{ly}" font-size="12" fill="#1f2a20">{lab}</text>')
    p.append(f'<text x="{w - pad}" y="{h - 10}" font-size="11" text-anchor="end" fill="#666">synthetic 16 km landscape from module 1, 250 m cells; v0.1</text>')
    p.append("</svg>")
    path.write_text("\n".join(p), encoding="utf-8")


def main() -> int:
    try:
        rules = MappingRules()
        g = load_handoff(ROOT / "data" / "handoff-module1.json")
        print(f"== Hand-off from module 1: {g.shape[0]} x {g.shape[1]} cells of {g.cell_m:.0f} m, "
              f"{g.available_mask().sum() * g.cell_ha:,.0f} ha available (from {g.provenance.get('branch')} @ {g.provenance.get('commit')}) ==")

        # 2. streams and flow
        filled = fill_depressions(g.layers["altitude_m"])
        rec = d8_receivers(filled)
        upstream_km2 = flow_accumulation(filled, rec) * g.cell_m ** 2 / 1e6
        stream = (upstream_km2 >= rules.stream_min_km2) & ~g.cover_is("WATER")
        flow = stream_flow_m3(upstream_km2, RUNOFF_MM)                       # (12, n, m) m3 per month
        sustainable = flow * (1 - rules.environmental_flow_fraction)
        lean = int(np.argmin(RUNOFF_MM))
        dry_ls = sustainable[lean] / SECONDS[lean] * 1000
        usable = stream & (dry_ls >= rules.min_dry_flow_ls)
        print(f"\n== Streams ==\n  {stream.sum() * g.cell_m / 1000:.1f} km of stream channel; {usable.sum() * g.cell_m / 1000:.1f} km give at least "
              f"{rules.min_dry_flow_ls:.0f} l/s sustainably in {MONTHS[lean]} (environmental flow {rules.environmental_flow_fraction:.0%} kept)")
        outlet = np.unravel_index(np.argmax(np.where(stream, upstream_km2, 0)), stream.shape)
        print(f"  largest stream: {upstream_km2[outlet]:.0f} km2 catchment, {dry_ls[outlet]:.0f} l/s sustainable in {MONTHS[lean]}, "
              f"{sustainable[7][outlet] / SECONDS[7] * 1000:,.0f} l/s in Aug")

        # 3. groundwater potential and springs
        rng = np.random.default_rng(5)
        fl = factor_layers(g, upstream_km2, stream, rng)
        gw_idx, gw_cls = groundwater_potential(fl["factors"], rules)
        print("\n== Groundwater potential (share of the landscape) ==")
        for c in GwClass:
            print(f"  {c.name:10s} {(gw_cls == c).mean():6.1%}")
        springs = find_springs(g, gw_idx, gw_cls, stream)
        points = []
        for i, j in zip(*np.nonzero(usable)):
            points.append(WaterPoint(f"ST-{i:02d}-{j:02d}", "stream", (int(i), int(j)), float(g.layers["altitude_m"][i, j]),
                                     tuple(float(v) for v in sustainable[:, i, j]), Confidence.INDICATIVE))
        dry_factor = np.array([.6, .55, .5, .5, .6, .8, 1, 1, 1, .9, .8, .7])
        for s, (i, j) in enumerate(springs):
            ls = 2 + 6 * float(gw_idx[i, j])                       # 2 to 8 l/s, higher where potential is higher
            m3 = tuple(float(ls / 1000 * sec * f * 0.7) for sec, f in zip(SECONDS, dry_factor))   # 30% left for drinking water
            points.append(WaterPoint(f"SP-{s + 1}", "spring", (i, j), float(g.layers["altitude_m"][i, j]), m3))
        print(f"  {len(springs)} spring sites at the foot of steep slopes; {sum(1 for p in points if p.kind == 'stream')} stream cells usable as sources")

        coef = np.vectorize(lambda c: rules.recharge_coef[Geology(c)])(fl["geology_code"])
        recharge_m3 = g.layers["rain_season_mm"] * coef * 10 * g.cell_ha            # m3 per cell per year
        gw_month = recharge_m3 * rules.recharge_share / 12

        # 4. access for available land
        wam = water_access(g.available_mask(), g.layers["altitude_m"], points, gw_cls, gw_month, g.cell_m, rules)
        ha = wam.hectares()
        avail_ha = g.available_mask().sum() * g.cell_ha
        print(f"\n== Water access for the {avail_ha:,.0f} ha of available land ==")
        for c in [AccessClass.GRAVITY, AccessClass.PUMPED, AccessClass.GROUNDWATER, AccessClass.HARVEST_ONLY]:
            print(f"  {c.name:13s} {ha[c.name]:8,.0f} ha  {ha[c.name] / avail_ha:6.1%}")

        # 5. how far the water stretches in the leanest month (irrigated wheat, the stage 02 budget)
        budget = build_budget(make_cluster(), PLANS, TMIN, TMAX, RAIN, season="dry")
        wheat = np.array(budget.demand_m3_per_ha["irrigated_wheat"])
        peak = int(np.argmax(wheat))
        print(f"\n== Can the water irrigate the land it reaches? (irrigated wheat, peak {MONTHS[peak]}: {wheat[peak]:,.0f} m3/ha) ==")
        # streams and springs have no storage: the peak month decides. An aquifer stores the rains, so
        # shallow wells are judged on a year's sustainable recharge against the whole season's demand.
        season_demand = float(wheat.sum())
        dep = wam.dependent_ha()
        irrigable_by_water, gw_ha, surf_ha = 0.0, 0.0, 0.0
        sources_summary = []
        for pid, dha in sorted(dep.items(), key=lambda x: -x[1]):
            p = wam.points[pid]
            if p.kind == "groundwater":
                ha_water = sum(p.sustainable_m3) / season_demand
                gw_ha += min(dha, ha_water)
            else:
                ha_water = p.sustainable_m3[peak] / wheat[peak]
                surf_ha += min(dha, ha_water)
                sources_summary.append({"id": pid, "kind": p.kind, "dependent_ha": dha, "water_for_ha": ha_water})
            irrigable_by_water += min(dha, ha_water)
        reach_ha = sum(dep.values())
        print(f"  land that some source reaches: {reach_ha:,.0f} ha; water for irrigated wheat in {MONTHS[peak]}: about {irrigable_by_water:,.0f} ha "
              f"({irrigable_by_water / reach_ha:.0%}): streams and springs {surf_ha:,.0f} ha, shallow wells {gw_ha:,.0f} ha "
              f"(wells judged on a year's recharge against the season's {season_demand:,.0f} m3/ha)")
        top = sorted(sources_summary, key=lambda s: -s["dependent_ha"])[:6]
        for s in top:
            print(f"  [DEBUG] {s['id']:10s} {s['kind']:7s} serves {s['dependent_ha']:6,.0f} ha, water for {s['water_for_ha']:6,.0f} ha in {MONTHS[peak]}")

        # one real record of the output contract, for the page: a field served by the busiest stream source
        best = next(t for t in top if t["kind"] == "stream")
        fi, fj = [int(v) for v in np.argwhere(wam.source_id == best["id"])[0]]
        sp = wam.points[best["id"]]
        example = {"field": {"cell": [fi, fj], "access": AccessClass(int(wam.access[fi, fj])).name, "source": best["id"],
                             "distance_km": round(float(wam.distance_km[fi, fj]), 2), "lift_m": round(float(wam.lift_m[fi, fj]), 1)},
                   "source": {"id": sp.point_id, "kind": sp.kind, "confidence": sp.confidence.value,
                              "sustainable_m3": [round(v) for v in sp.sustainable_m3],
                              "dependent_ha": round(best["dependent_ha"], 1), "water_for_wheat_ha_in_feb": round(best["water_for_ha"], 1)},
                   "rules_version": "0.1", "from_module_1": {k: g.provenance.get(k) for k in ("branch", "commit")}}
        maps_svg(g, stream, rec, upstream_km2, springs, gw_cls, wam, ROOT / "assets" / "water-maps.svg")
        out = {"note": "Synthetic landscape from module 1; indicative rules v0.1. Not real water.",
               "provenance": g.provenance, "available_ha": avail_ha, "access_ha": {k: v for k, v in ha.items() if k != "NOT_ASSESSED"},
               "stream_km": float(stream.sum() * g.cell_m / 1000), "usable_stream_km": float(usable.sum() * g.cell_m / 1000),
               "springs": len(springs), "gw_share": {c.name: float((gw_cls == c).mean()) for c in GwClass},
               "lean_month": MONTHS[lean], "peak_demand_month": MONTHS[peak], "wheat_peak_m3_per_ha": float(wheat[peak]),
               "reached_ha": reach_ha, "irrigable_by_water_ha": irrigable_by_water, "groundwater_irrigable_ha": gw_ha,
               "surface_irrigable_ha": surf_ha, "wheat_season_m3_per_ha": season_demand,
               "top_sources": top, "runoff_mm": RUNOFF_MM, "example_record": example,
               "rules": {"environmental_flow_fraction": rules.environmental_flow_fraction, "gravity_max_km": rules.gravity_max_km,
                         "pump_max_km": rules.pump_max_km, "pump_max_lift_m": rules.pump_max_lift_m, "recharge_share": rules.recharge_share}}
        (ROOT / "assets" / "demo-water-availability.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print("  [DEBUG] wrote assets/water-maps.svg and assets/demo-water-availability.json")
        return 0
    except (KeyError, ValueError, FileNotFoundError) as e:
        print(f"[DATA ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Irrigated land suitability demo (Phase 1, module 3) on the SYNTHETIC landscape of modules 1 and 2.

  1. Read module 1's hand-off (land) and module 2's hand-off (water access, sources, climate).
  2. Class every available field for surface, sprinkler and drip irrigation (worst factor wins).
  3. Group fields into command areas by serving source; water-limited hectares per method.
  4. Write assets/irrigation-maps.svg, assets/demo-irrigated-suitability.json and the module 3
     hand-off assets/handoff-irrigated-suitability.json for module 4.

Run from the branch root:  python3 src/demo_irrigation.py   (after src/demo_water_map.py)
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from water_res import (MONTHS, IrrigationMethod, assess_irrigation, command_areas, load_handoff,  # noqa: E402
                       load_water_handoff, reference_gross_m3_per_ha)
from water_res.irrigation import MISSING_FACTORS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLS_COL = {3: "#1a9641", 2: "#a6d96a", 1: "#fdae61", 0: "#d7191c", -1: "#ebe6db"}
METHOD_COL = {"surface": "#8a6d3b", "sprinkler": "#2a78d6", "drip": "#159a6e", "": "#ebe6db", "weak": "#e4d9bf"}


def raster(vals, cols, x0, y0, cell, n):
    out = []
    for i in range(n):
        j = 0
        while j < n:
            v = vals[i, j]; j0 = j
            while j < n and vals[i, j] == v:
                j += 1
            out.append(f'<rect x="{x0 + j0 * cell}" y="{y0 + i * cell}" width="{(j - j0) * cell}" height="{cell}" fill="{cols[v]}"/>')
    return out


def maps_svg(suit, path: Path, n: int, cell: int = 4) -> None:
    pad, gap, top, size = 12, 26, 34, n * cell
    w, h = pad * 2 + 3 * size + 2 * gap, top + size + 94
    best = np.where(suit.best_rank >= 2, suit.best_method, np.where(suit.best_rank == 1, "weak", ""))
    panels = [("1. Surface irrigation (furrow, basin)", suit.rank[IrrigationMethod.SURFACE], CLS_COL),
              ("2. Drip irrigation", suit.rank[IrrigationMethod.DRIP], CLS_COL),
              ("3. Best method (S1 or S2)", best, METHOD_COL)]
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Helvetica, Arial, sans-serif" role="img" shape-rendering="crispEdges" '
         f'aria-label="Three synthetic maps: suitability for surface irrigation, suitability for drip irrigation, and the best method per field.">',
         f'<rect width="{w}" height="{h}" fill="#fbfaf6"/>']
    for k, (title, vals, cols) in enumerate(panels):
        x0 = pad + k * (size + gap)
        p.append(f'<text x="{x0}" y="22" font-size="13.5" font-weight="bold" fill="#1f2a20">{title}</text>')
        p += raster(vals, cols, x0, top, cell, n)
        p.append(f'<rect x="{x0}" y="{top}" width="{size}" height="{size}" fill="none" stroke="#b9b2a2"/>')
    legends = [[("S1", CLS_COL[3]), ("S2", CLS_COL[2]), ("S3", CLS_COL[1]), ("N", CLS_COL[0]), ("not available", CLS_COL[-1])]] * 2 + \
              [[("surface", METHOD_COL["surface"]), ("sprinkler", METHOD_COL["sprinkler"]), ("drip", METHOD_COL["drip"]),
                ("S3 only", METHOD_COL["weak"]), ("not available", METHOD_COL[""])]]
    for k, items in enumerate(legends):
        x0 = pad + k * (size + gap)
        for idx, (lab, col) in enumerate(items):
            lx, ly = x0 + (idx % 3) * (size // 3), top + size + 20 + (idx // 3) * 18
            p.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="2" fill="{col}"/><text x="{lx + 17}" y="{ly}" font-size="12" fill="#1f2a20">{lab}</text>')
    p.append(f'<text x="{w - pad}" y="{h - 10}" font-size="11" text-anchor="end" fill="#666">synthetic landscape of modules 1 and 2, 250 m cells; v0.1</text>')
    p.append("</svg>")
    path.write_text("\n".join(p), encoding="utf-8")


def main() -> int:
    try:
        land = load_handoff(ROOT / "data" / "handoff-module1.json")
        water = load_water_handoff(ROOT / "assets" / "handoff-water-availability.json")
        if water.access.shape != land.shape:
            raise ValueError(f"module 1 grid {land.shape} and module 2 grid {water.access.shape} differ")
        avail = land.available_mask()
        print(f"== Inputs: {avail.sum() * land.cell_ha:,.0f} ha available (module 1), {len(water.sources)} water sources (module 2) ==")

        suit = assess_irrigation(land.layers, avail, water.access_name(), land.cell_ha)
        print("\n== Irrigated land suitability (available land only) ==")
        summary = {}
        for m in IrrigationMethod:
            ha = suit.hectares(m)
            summary[m.value] = ha
            lim, cnt = np.unique(suit.limiting[m][(suit.rank[m] >= 0) & (suit.rank[m] < 3)], return_counts=True)
            top = lim[np.argmax(cnt)] if len(cnt) else "-"
            print(f"  {m.value:10s} " + "  ".join(f"{k} {v:7,.0f} ha" for k, v in ha.items()) + f"  | most common limit: {top}")
        best_ha = {mv: float(((suit.best_method == mv) & (suit.best_rank >= 2)).sum() * land.cell_ha) for mv in ("surface", "sprinkler", "drip")}
        print("  best method on S1/S2 land: " + ", ".join(f"{k} {v:,.0f} ha" for k, v in best_ha.items()))
        print(f"  [DEBUG] factors not yet assessed: {', '.join(MISSING_FACTORS)}")

        cas = command_areas(suit, water, land.layers["altitude_m"])
        totals = {m.value: sum(c.irrigable_ha(m.value) for c in cas) for m in IrrigationMethod}
        suitable = {m.value: sum(c.suitable_ha(m.value) for c in cas) for m in IrrigationMethod}
        best_mix = sum(max(c.irrigable_ha(m.value) for m in IrrigationMethod) for c in cas)
        print(f"\n== Land and water together ({len(cas)} command areas) ==")
        for m in IrrigationMethod:
            print(f"  all {m.value:10s}: suitable S1/S2 {suitable[m.value]:7,.0f} ha, irrigable with the dry-season water {totals[m.value]:7,.0f} ha")
        print(f"  best method per command area: {best_mix:,.0f} ha irrigable")
        dem = {m.value: reference_gross_m3_per_ha(water.et0_mm_day, water.rain_mm, m) for m in IrrigationMethod}
        peak = int(np.argmax(dem["surface"]))
        print(f"  [DEBUG] reference demand (Kc 1.0) peaks in {MONTHS[peak]}: surface {dem['surface'][peak]:,.0f}, "
              f"sprinkler {dem['sprinkler'][peak]:,.0f}, drip {dem['drip'][peak]:,.0f} m3/ha")

        top_cas = sorted(cas, key=lambda c: -max(c.irrigable_ha(m.value) for m in IrrigationMethod))[:12]
        for c in top_cas[:5]:
            bm = max(IrrigationMethod, key=lambda m: c.irrigable_ha(m.value))
            print(f"  [DEBUG] {c.source_id:10s} {c.kind:11s} suitable {c.suitable_ha(bm.value):6,.0f} ha ({bm.value}), irrigable {c.irrigable_ha(bm.value):6,.0f} ha")

        maps_svg(suit, ROOT / "assets" / "irrigation-maps.svg", land.shape[0])

        def ca_record(c):
            bm = max(IrrigationMethod, key=lambda m: c.irrigable_ha(m.value))
            return {"source_id": c.source_id, "kind": c.kind, "mean_altitude_m": round(c.mean_altitude_m),
                    "best_method": bm.value, "suitable_ha": {m.value: round(c.suitable_ha(m.value), 1) for m in IrrigationMethod},
                    "irrigable_ha": {m.value: round(c.irrigable_ha(m.value), 1) for m in IrrigationMethod},
                    "sustainable_m3": [round(v) for v in c.sustainable_m3]}

        out = {"note": "Synthetic landscape of modules 1 and 2; indicative requirements v0.1. Not real land or water.",
               "hectares_by_method": summary, "best_method_ha": best_ha, "suitable_ha": suitable,
               "irrigable_ha": totals, "best_mix_irrigable_ha": best_mix, "command_areas": len(cas),
               "reference_peak_month": MONTHS[peak], "reference_peak_m3_per_ha": {k: float(v[peak]) for k, v in dem.items()},
               "top_command_areas": [ca_record(c) for c in top_cas[:6]], "missing_factors": list(MISSING_FACTORS),
               "irrigable_by_kind": {k: {m.value: sum(c.irrigable_ha(m.value) for c in cas if c.kind == k) for m in IrrigationMethod}
                                     for k in ("stream", "spring", "groundwater")}}
        (ROOT / "assets" / "demo-irrigated-suitability.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

        # shallow-well sites each water well under a hectare; pool them as one "shallow-well plots" record
        # (irrigable = the sum of each site's own limit, never the limit of a summed pool)
        wells = [c for c in cas if c.kind == "groundwater"]
        pooled = []
        if wells:
            pooled.append({"source_id": "WELLS-POOLED", "kind": "groundwater", "sites": len(wells),
                           "mean_altitude_m": round(float(np.mean([c.mean_altitude_m for c in wells]))),
                           "best_method": max(IrrigationMethod, key=lambda m: sum(c.irrigable_ha(m.value) for c in wells)).value,
                           "suitable_ha": {m.value: round(sum(c.suitable_ha(m.value) for c in wells), 1) for m in IrrigationMethod},
                           "irrigable_ha": {m.value: round(sum(c.irrigable_ha(m.value) for c in wells), 1) for m in IrrigationMethod},
                           "sustainable_m3": [round(v) for v in np.sum([c.sustainable_m3 for c in wells], axis=0)]})
            print(f"  [DEBUG] {len(wells)} shallow-well sites pooled: irrigable with drip {pooled[0]['irrigable_ha']['drip']:,.1f} ha")
        handoff = {"contract": "aiae.phase1.irrigated_suitability", "version": "0.1", "producer": "stage/02-water-resources src/demo_irrigation.py",
                   "note": "Command areas with irrigable land and their water. Synthetic; indicative v0.1.",
                   "command_areas": [ca_record(c) for c in sorted(cas, key=lambda c: -max(c.irrigable_ha(m.value) for m in IrrigationMethod))
                                     if c.kind != "groundwater" and max(c.irrigable_ha(m.value) for m in IrrigationMethod) >= 1.0] + pooled,
                   "method_efficiency": {m.value: m.efficiency for m in IrrigationMethod},
                   "climate": {"months": list(MONTHS), "et0_mm_day": [round(float(v), 2) for v in water.et0_mm_day], "rain_mm": [float(v) for v in water.rain_mm]},
                   "from_module_2": water.provenance}
        hp = ROOT / "assets" / "handoff-irrigated-suitability.json"
        hp.write_text(json.dumps(handoff, indent=1), encoding="utf-8")
        print(f"\n  [DEBUG] wrote assets/irrigation-maps.svg, assets/demo-irrigated-suitability.json and {hp.name} "
              f"({len(handoff['command_areas'])} command areas of at least 1 ha)")
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

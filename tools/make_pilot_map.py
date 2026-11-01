#!/usr/bin/env python3
"""
Build pilot-map.html: an illustrated, interactive map of a FICTIONAL pilot woreda that shows
where each stage of the chain lives on the ground. Every place, value and shape is synthetic.

Layers (toggled on the page):
  suitability (01)  kebeles coloured S1 to N for teff
  water (02)        river, irrigation scheme, shallow wells
  climate (03)      rainfall isohyets and weather stations
  clusters (04, 07) planning clusters A, B, C
  inputs (06)       cooperative stores
  monitoring (08)   plots flagged from space
  storage (09, 10)  collection centres
  roads (11)        asphalt, gravel, and earth roads that close in the rains
  market (05, 12)   market town and the buyer

Usage (from the repository root, on main):
  python3 tools/make_pilot_map.py        # writes pilot-map.html and assets/img/pilot-map.svg
Needs numpy and scipy (Voronoi kebele boundaries). Run make_tools_page.py first: the page
header is reused from tools.html.
"""
from __future__ import annotations

import math
import sys
import traceback
from html import escape as E
from pathlib import Path

import numpy as np
from scipy.spatial import Voronoi

ROOT = Path(__file__).resolve().parent.parent
W, H = 1200, 760
CX, CY, RX, RY = 590, 390, 500, 315
RNG = np.random.default_rng(20261101)
CLS = {"S1": "#1f7a45", "S2": "#7fb069", "S3": "#e3a64b", "N": "#c4553b"}
CLS_TEXT = {"S1": "#fff", "S2": "#1f2a20", "S3": "#1f2a20", "N": "#fff"}
CLUSTER = {"A": "#74582a", "B": "#3f6b34", "C": "#2f5d8a"}
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif'


# ------------------------------------------------------------------ domain model of the fictional woreda
def boundary_points(n: int = 72) -> np.ndarray:
    """A smooth, irregular woreda outline (polar radius with a few low-frequency waves)."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r = 1 + 0.07 * np.sin(3 * t + 0.6) + 0.05 * np.sin(5 * t + 1.9) + 0.03 * np.cos(7 * t)
    return np.c_[CX + RX * r * np.cos(t), CY + RY * r * np.sin(t)]


def smooth_path(pts: np.ndarray, closed: bool = True) -> str:
    """Catmull-Rom through the points, written as cubic Beziers."""
    p = list(map(tuple, pts))
    n = len(p)
    out = [f"M{p[0][0]:.1f},{p[0][1]:.1f}"]
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0, p1, p2, p3 = p[(i - 1) % n], p[i], p[(i + 1) % n], p[(i + 2) % n]
        if not closed:
            p0 = p[max(i - 1, 0)]
            p3 = p[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(out) + (" Z" if closed else "")


def kebele_seeds() -> np.ndarray:
    """14 kebele centres on a jittered lattice inside the outline."""
    seeds = []
    for gy in range(3):
        cols = [4, 6, 4][gy]
        for gx in range(cols):
            x = CX - RX * 0.78 + (gx + 0.5) * (RX * 1.56 / cols)
            y = CY - RY * 0.62 + gy * RY * 0.62
            seeds.append((x + RNG.uniform(-28, 28), y + RNG.uniform(-22, 22)))
    return np.array(seeds)


def kebele_class(x: float, y: float) -> tuple[str, str]:
    """Teff suitability and the main limit, from position: escarpment east, Vertisol valley south-west."""
    if x > CX + RX * 0.55:
        return ("N", "slope over 30%") if y < CY else ("S3", "slope 15 to 30%")
    if x < CX - RX * 0.35 and y > CY + 20:
        return "S2", "poor drainage (Vertisol)"
    if y < CY - RY * 0.45:
        return "S2", "soil acidity (pH 5.2)"
    return "S1", "none"


def voronoi_cells(seeds: np.ndarray) -> list[np.ndarray]:
    far = np.array([[-3000, -3000], [4200, -3000], [-3000, 4200], [4200, 4200]])
    vor = Voronoi(np.vstack([seeds, far]))
    cells = []
    for i in range(len(seeds)):
        region = vor.regions[vor.point_region[i]]
        if -1 in region or not region:
            raise ValueError(f"kebele {i + 1}: open Voronoi region")
        cells.append(vor.vertices[region])
    return cells


# ------------------------------------------------------------------ drawing helpers
def poly(pts: np.ndarray) -> str:
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"


def tip(text: str) -> str:
    return f' data-tip="{E(text)}"'


def house(x, y, fill, roof, label, t, s=1.0):
    return (f'<g class="feat" transform="translate({x} {y}) scale({s})"{tip(t)}>'
            f'<path d="M-16 0 v-16 l16 -12 l16 12 v16 z" fill="{fill}" stroke="#4a3a22" stroke-width="1.2"/>'
            f'<path d="M-19 -15 l19 -15 l19 15" fill="none" stroke="{roof}" stroke-width="4" stroke-linecap="round"/>'
            f'<rect x="-5" y="-10" width="10" height="10" fill="#6b4f2a"/></g>'
            + (f'<text x="{x}" y="{y + 16 * s}" class="lbl" text-anchor="middle">{E(label)}</text>' if label else ""))


def warehouse(x, y, label, t):
    return (f'<g class="feat" transform="translate({x} {y})"{tip(t)}>'
            f'<rect x="-30" y="-24" width="60" height="26" fill="#efe3c8" stroke="#6b4f2a" stroke-width="1.4"/>'
            f'<path d="M-34 -22 L0 -40 L34 -22" fill="none" stroke="#9a4a28" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<rect x="-8" y="-14" width="16" height="16" fill="#6b4f2a"/>'
            f'<rect x="34" y="-34" width="10" height="36" rx="5" fill="#cfc6b4" stroke="#7a6a50"/><rect x="47" y="-30" width="10" height="32" rx="5" fill="#cfc6b4" stroke="#7a6a50"/></g>'
            f'<text x="{x + 8}" y="{y + 18}" class="lbl b" text-anchor="middle">{E(label)}</text>')


def curve(a, b, bend=0.12):
    (x1, y1), (x2, y2) = a, b
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    return f"M{x1:.1f},{y1:.1f} Q{mx - dy * bend:.1f},{my + dx * bend:.1f} {x2:.1f},{y2:.1f}"


# ------------------------------------------------------------------ the map
def build_svg() -> tuple[str, list[dict]]:
    bpts = boundary_points()
    outline = smooth_path(bpts)
    seeds = kebele_seeds()
    cells = voronoi_cells(seeds)
    keb = []
    for i, (s, c) in enumerate(zip(seeds, cells)):
        cls, limit = kebele_class(*s)
        cluster = "A" if s[0] < CX - 150 else ("B" if s[0] < CX + 170 else "C")
        keb.append({"id": f"K{i + 1:02d}", "x": float(s[0]), "y": float(s[1]), "cls": cls, "limit": limit, "cluster": cluster, "cell": c,
                    "hh": int(RNG.integers(60, 140))})

    g = []
    g.append(f'<svg xmlns="http://www.w3.org/2000/svg" id="pmap" viewBox="0 0 {W} {H}" font-family=\'{FONT}\' role="img" aria-labelledby="pm-t pm-d">')
    g.append('<title id="pm-t">Illustrated map of a fictional pilot woreda</title>')
    g.append('<desc id="pm-d">Fourteen kebeles coloured by teff suitability, a river and irrigation scheme, rainfall lines, planning clusters A to C, '
             'cooperative stores, plots flagged from space, two collection centres, roads that close in the rains and the market town. All places are fictional.</desc>')
    g.append(f'''<defs>
  <clipPath id="woreda"><path d="{outline}"/></clipPath>
  <pattern id="hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="10" stroke="#8a7a5c" stroke-width="2" opacity=".35"/></pattern>
  <pattern id="irr" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#cde6c3"/><line x1="0" y1="4" x2="8" y2="4" stroke="#5aa0c8" stroke-width="1.6"/></pattern>
  <radialGradient id="lake" cx=".45" cy=".4" r=".7"><stop offset="0" stop-color="#9fcbe6"/><stop offset="1" stop-color="#5f9fc9"/></radialGradient>
  <filter id="soft" x="-5%" y="-5%" width="110%" height="110%"><feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#1f2a20" flood-opacity=".18"/></filter>
  <style>
    .lbl {{ font-size: 12px; font-weight: 600; fill: #1f2a20; paint-order: stroke; stroke: #fbfaf6; stroke-width: 3.5px; stroke-linejoin: round; }}
    .lbl.b {{ font-weight: 800; font-size: 13px; }}
    .kname {{ font-size: 11.5px; font-weight: 700; paint-order: stroke; stroke-width: 3px; stroke-linejoin: round; }}
    .feat, .keb {{ cursor: help; }}
    .keb:hover path, .keb:focus path {{ stroke: #1f2a20; stroke-width: 3; }}
    .feat:hover {{ filter: brightness(1.08); }}
  </style>
</defs>''')
    # paper and surroundings
    g.append(f'<rect width="{W}" height="{H}" fill="#eef1e6"/>')
    g.append('<g opacity=".5" stroke="#b9c4a8" fill="none" stroke-width="1.2">' + "".join(
        f'<path d="{smooth_path(np.c_[CX + (RX + 40 + k * 26) * np.cos(t), CY + (RY + 30 + k * 20) * np.sin(t)])}"/>'
        for k in range(3) for t in [np.linspace(0, 2 * np.pi, 40, endpoint=False)]) + "</g>")
    g.append(f'<path d="{outline}" fill="#f6f1e2" filter="url(#soft)"/>')

    # ---- suitability layer (kebele cells), with a neutral version when the layer is off
    g.append('<g clip-path="url(#woreda)">')
    g.append('<g class="layer" data-layer="suitability">')
    for k in keb:
        t = (f"Kebele {k['id'][1:]} (fictional) · teff suitability {k['cls']} · main limit: {k['limit']} · "
             f"cluster {k['cluster']} · about {k['hh']} households")
        g.append(f'<g class="keb" tabindex="0" role="img" aria-label="{E(t)}"{tip(t)}><path d="{poly(k["cell"])}" fill="{CLS[k["cls"]]}" fill-opacity=".62" stroke="#fbfaf6" stroke-width="2"/></g>')
    g.append("</g>")
    g.append('<g class="layer-off" data-off="suitability" style="display:none">' + "".join(
        f'<path d="{poly(k["cell"])}" fill="#efe6cf" stroke="#d8ccae" stroke-width="1.5"/>' for k in keb) + "</g>")
    # escarpment hatching (east) and the lake (south-west)
    g.append(f'<path d="M{CX + RX * 0.52},{CY - RY * 1.2} C{CX + RX * 0.62},{CY - 40} {CX + RX * 0.48},{CY + 80} {CX + RX * 0.6},{CY + RY * 1.2} L{W},{H} L{W},0 Z" fill="url(#hatch)"/>')
    g.append("</g>")
    g.append(f'<text x="{CX + RX * 0.97}" y="{CY - RY * 0.5}" class="lbl" text-anchor="middle">escarpment</text>')
    lake = (CX - RX * 0.66, CY + RY * 0.62)
    g.append(f'<g class="feat"{tip("Lake (fictional): the river ends here; the valley around it has heavy, poorly drained Vertisols")}>'
             f'<ellipse cx="{lake[0]}" cy="{lake[1]}" rx="92" ry="44" fill="url(#lake)" stroke="#4f86ad" stroke-width="1.5"/></g>')
    g.append(f'<text x="{lake[0]}" y="{lake[1] + 5}" class="lbl" text-anchor="middle" style="fill:#183b55">Lake</text>')

    # ---- climate layer: isohyets and stations (03)
    g.append('<g class="layer" data-layer="climate">')
    for k, (yy, mm) in enumerate([(CY - RY * 0.55, 1100), (CY - RY * 0.05, 950), (CY + RY * 0.5, 800)]):
        pts = np.array([[x, yy + 26 * math.sin(x / 140 + k)] for x in np.linspace(CX - RX * 0.95, CX + RX * 0.95, 9)])
        g.append(f'<path d="{smooth_path(pts, closed=False)}" fill="none" stroke="#2a78d6" stroke-width="1.6" stroke-dasharray="2 6" stroke-linecap="round" clip-path="url(#woreda)"/>')
        side, anchor, dx = (pts[-1], "start", 8) if mm == 800 else (pts[0], "end", -8)
        g.append(f'<text x="{side[0] + dx:.0f}" y="{side[1] + 4:.0f}" class="lbl" text-anchor="{anchor}" style="fill:#1d5ca8">{mm} mm</text>')
    for (x, y, name) in [(CX - 200, CY - 205, "Station 1"), (CX + 120, CY + 40, "Station 2")]:
        g.append(f'<g class="feat"{tip(f"{name} (fictional): daily rain and temperature for the season outlook (stage 03)")}>'
                 f'<rect x="{x - 4}" y="{y - 26}" width="8" height="26" fill="#5d6d7e"/><circle cx="{x}" cy="{y - 30}" r="8" fill="#2a78d6" stroke="#fff" stroke-width="2"/></g>')
    g.append("</g>")

    # ---- water layer: river, diversion, irrigation scheme, wells (02)
    river = np.array([[CX + RX * 0.95, CY - RY * 0.95], [CX + RX * 0.55, CY - RY * 0.55], [CX + RX * 0.15, CY - RY * 0.32], [CX - RX * 0.1, CY - RY * 0.05],
                      [CX - RX * 0.3, CY + RY * 0.22], [lake[0] + 40, lake[1] - 30]])
    g.append('<g class="layer" data-layer="water">')
    scheme = np.array([[CX - RX * 0.3, CY - RY * 0.02], [CX - RX * 0.08, CY + RY * 0.08], [CX - RX * 0.14, CY + RY * 0.3], [CX - RX * 0.38, CY + RY * 0.22]])
    g.append(f'<g class="feat"{tip("Irrigation scheme (fictional): about 100 ha of dry-season wheat and onion, limited by February and March water (stage 02)")}>'
             f'<path d="{poly(scheme)}" fill="url(#irr)" stroke="#2f7fb5" stroke-width="1.5"/></g>')
    g.append(f'<path d="{smooth_path(river, closed=False)}" fill="none" stroke="#4f97c9" stroke-width="7" stroke-linecap="round"/>')
    g.append(f'<path d="{smooth_path(river, closed=False)}" fill="none" stroke="#9fd0ee" stroke-width="2.5" stroke-linecap="round"/>')
    dv = river[3]
    g.append(f'<g class="feat"{tip("River diversion (fictional): 30% of the flow stays in the river as environmental flow")}>'
             f'<rect x="{dv[0] - 8}" y="{dv[1] - 8}" width="16" height="16" rx="3" fill="#2f5d8a" stroke="#fff" stroke-width="2"/></g>')
    g.append(f'<text x="{scheme[0][0] - 10:.0f}" y="{scheme[0][1] - 8:.0f}" class="lbl" style="fill:#1f5f8a">irrigation scheme</text>')
    for (x, y) in [(CX - RX * 0.5, CY - RY * 0.2), (CX + RX * 0.05, CY + RY * 0.4), (CX + RX * 0.3, CY + RY * 0.1)]:
        g.append(f'<g class="feat"{tip("Shallow well (fictional): pumping is kept below 40% of recharge")}><circle cx="{x:.0f}" cy="{y:.0f}" r="7" fill="#fff" stroke="#2f7fb5" stroke-width="3"/><circle cx="{x:.0f}" cy="{y:.0f}" r="2.5" fill="#2f7fb5"/></g>')
    g.append("</g>")

    # ---- clusters layer (04, 07)
    g.append('<g class="layer" data-layer="clusters">')
    for k in keb:
        g.append(f'<path d="{poly(k["cell"])}" fill="none" stroke="{CLUSTER[k["cluster"]]}" stroke-width="3.5" stroke-dasharray="10 6" clip-path="url(#woreda)" pointer-events="none"/>')
    for c, col in CLUSTER.items():
        xs = [k["x"] for k in keb if k["cluster"] == c]
        ys = [k["y"] for k in keb if k["cluster"] == c]
        x, y = sum(xs) / len(xs), min(ys) - 4
        n = len(xs)
        g.append(f'<g class="feat"{tip(f"Planning cluster {c} (fictional): {n} kebeles planned together by stage 04; plots assigned and followed by stage 07")}>'
                 f'<circle cx="{x:.0f}" cy="{y:.0f}" r="19" fill="{col}" stroke="#fff" stroke-width="3"/>'
                 f'<text x="{x:.0f}" y="{y + 6:.0f}" text-anchor="middle" font-size="17" font-weight="900" fill="#fff">{c}</text></g>')
    g.append("</g>")

    # kebele names (always on)
    g.append('<g pointer-events="none">' + "".join(
        f'<text x="{k["x"]:.0f}" y="{k["y"] + 26:.0f}" class="kname" text-anchor="middle" style="fill:#1f2a20;stroke:#fbfaf6">{k["id"]}</text>' for k in keb) + "</g>")

    # ---- roads layer (11) and collection centres
    cc = [(CX - RX * 0.28, CY + RY * 0.42), (CX + RX * 0.3, CY - RY * 0.02)]
    town = (CX + RX * 1.04, CY + RY * 0.12)
    g.append('<g class="layer" data-layer="roads">')
    asphalt = np.array([[CX - RX * 1.08, CY + RY * 0.55], cc[0], [CX, CY + RY * 0.18], cc[1], [CX + RX * 0.7, CY + RY * 0.18], town])
    g.append(f'<path d="{smooth_path(asphalt, closed=False)}" fill="none" stroke="#5a5a5a" stroke-width="9" stroke-linecap="round"/>')
    g.append(f'<path d="{smooth_path(asphalt, closed=False)}" fill="none" stroke="#f2f2f2" stroke-width="1.5" stroke-dasharray="10 9"/>')
    closes = []
    for k in keb:
        hub = cc[0] if k["x"] < CX else cc[1]
        d = curve(hub, (k["x"], k["y"]), 0.1)
        earth = k["cls"] in ("S3", "N") or k["id"] in ("K01", "K11")
        if earth:
            g.append(f'<path d="{d}" fill="none" stroke="#9a6b3a" stroke-width="3" stroke-dasharray="7 5" stroke-linecap="round"/>')
            closes.append(k)
        else:
            g.append(f'<path d="{d}" fill="none" stroke="#b9a27a" stroke-width="2.6" stroke-linecap="round" opacity=".9"/>')
    for k in closes[:4]:
        hub = cc[0] if k["x"] < CX else cc[1]
        mx, my = hub[0] + (k["x"] - hub[0]) * 0.62, hub[1] + (k["y"] - hub[1]) * 0.62   # nearer the kebele, clear of the centre's label
        kid = k["id"]
        g.append(f'<g class="feat"{tip(f"Earth road to {kid} closes in the rains: trucks detour, so grain should move before July (stages 10, 11)")}>'
                 f'<circle cx="{mx:.0f}" cy="{my:.0f}" r="10" fill="#fff" stroke="#b3161a" stroke-width="2.5"/>'
                 f'<path d="M{mx - 4:.0f},{my - 4:.0f} l8,8 M{mx + 4:.0f},{my - 4:.0f} l-8,8" stroke="#b3161a" stroke-width="2.5" stroke-linecap="round"/></g>')
    g.append("</g>")

    # ---- inputs layer: cooperative stores (06)
    g.append('<g class="layer" data-layer="inputs">')
    for k in [keb[1], keb[6], keb[11]]:
        g.append(house(k["x"] + 30, k["y"] - 6, "#f3e6c4", "#3f6b34", "",
                       f"Cooperative store near {k['id']} (fictional): seed and fertilizer ordered back from planting day (stage 06)", 0.85))
    g.append("</g>")

    # ---- monitoring layer: flagged plots (08)
    g.append('<g class="layer" data-layer="monitoring">')
    for k in [keb[4], keb[9], keb[12]]:
        x, y = k["x"] - 30, k["y"] - 12
        kid = k["id"]
        g.append(f'<g class="feat"{tip(f"Plots near {kid} flagged from space: NDVI below the normal range for 10 days (stage 08); an agent visit is scheduled (stage 07)")}>'
                 + "".join(f'<rect x="{x + (j % 3) * 9:.0f}" y="{y + (j // 3) * 9:.0f}" width="8" height="8" fill="{["#2f9e5a", "#2f9e5a", "#e3a64b", "#2f9e5a", "#c4553b", "#2f9e5a"][j]}"/>' for j in range(6))
                 + f'<path d="M{x + 32:.0f},{y - 10:.0f} l9,16 h-18 z" fill="#f2c14e" stroke="#7a5a00" stroke-width="1.5"/><text x="{x + 32:.0f}" y="{y + 4:.0f}" text-anchor="middle" font-size="11" font-weight="900" fill="#3a2a00">!</text></g>')
    g.append("</g>")

    # ---- storage layer: collection centres (09, 10)
    g.append('<g class="layer" data-layer="storage">')
    g.append(warehouse(cc[0][0], cc[0][1], "Collection centre 1",
                       "Collection centre 1 (fictional): harvest lots are dried, graded and stored in hermetic bags (stages 09, 10)"))
    g.append(warehouse(cc[1][0], cc[1][1], "Collection centre 2",
                       "Collection centre 2 (fictional): stock peaks 8 to 13 weeks after harvest starts, so deliveries are scheduled early (stage 10)"))
    g.append("</g>")

    # ---- market layer (05, 12)
    g.append('<g class="layer" data-layer="market">')
    tx, ty = town
    g.append(f'<g class="feat"{tip("Market town (fictional): weekly market and the flour mill that buys under a price-band contract (stages 05, 12)")}>'
             f'<rect x="{tx - 44}" y="{ty - 62}" width="88" height="70" rx="12" fill="#fff" stroke="#9a4a28" stroke-width="2" filter="url(#soft)"/>'
             + "".join(f'<path d="M{tx - 34 + j * 24} {ty - 24} v-14 h18 v14" fill="{["#e9b949", "#9a4a28", "#3f6b34"][j]}"/>' for j in range(3))
             + f'<path d="M{tx - 36} {ty - 40} h72" stroke="#9a4a28" stroke-width="5" stroke-linecap="round"/>'
             f'<circle cx="{tx - 18}" cy="{ty - 8}" r="6" fill="#e9b949"/><circle cx="{tx}" cy="{ty - 8}" r="6" fill="#7fb069"/><circle cx="{tx + 18}" cy="{ty - 8}" r="6" fill="#e9b949"/></g>')
    g.append(f'<text x="{tx}" y="{ty + 26}" class="lbl b" text-anchor="middle">Market town</text>')
    g.append(f'<text x="{tx}" y="{ty + 42}" class="lbl" text-anchor="middle">buyer · flour mill</text>')
    g.append("</g>")

    # frame text
    g.append(f'<path d="{outline}" fill="none" stroke="#6b5a3a" stroke-width="2.5"/>')
    g.append(f'<text x="34" y="44" font-size="20" font-weight="800" fill="#1f2a20">A fictional pilot woreda</text>')
    g.append(f'<text x="34" y="66" font-size="13" fill="#5d665e">Illustrative only: no real kebele, road or farmer</text>')
    # compass and scale
    g.append(f'<g transform="translate({W - 60} 60)"><circle r="22" fill="#fff" stroke="#b9c4a8"/><path d="M0 -16 L6 4 L0 0 L-6 4 Z" fill="#1f2a20"/><text y="-26" text-anchor="middle" font-size="12" font-weight="800" fill="#1f2a20">N</text></g>')
    g.append(f'<g transform="translate(40 {H - 34})"><rect width="100" height="6" fill="#1f2a20"/><rect x="50" width="50" height="6" fill="#fff" stroke="#1f2a20"/>'
             f'<text y="22" font-size="11.5" fill="#5d665e">0</text><text x="100" y="22" font-size="11.5" fill="#5d665e" text-anchor="middle">about 5 km</text></g>')
    g.append("</svg>")
    return "\n".join(g), keb


LAYERS = [("suitability", "01", "Land suitability (teff)", "Kebeles coloured S1 to N; hover for the main limit."),
          ("water", "02", "Water", "River, diversion, irrigation scheme and wells."),
          ("climate", "03", "Rainfall and stations", "Season rainfall lines and the stations behind the outlook."),
          ("clusters", "04 · 07", "Planning clusters", "Kebeles planned and followed together."),
          ("inputs", "06", "Cooperative stores", "Where seed and fertilizer are delivered."),
          ("monitoring", "08", "Flagged plots", "Plots behind the healthy NDVI curve."),
          ("storage", "09 · 10", "Collection centres", "Drying, grading and storage."),
          ("roads", "11", "Roads", "Asphalt, gravel, and earth roads that close in the rains."),
          ("market", "05 · 12", "Market town", "The buyer, the contract and the settlement.")]


def build_page(svg: str, keb: list[dict]) -> str:
    tools = (ROOT / "tools.html").read_text(encoding="utf-8")
    header = tools.split("<main", 1)[0]
    rep = {
        "<title>Calculators | AIAE</title>": "<title>Pilot Map | AIAE</title>",
        "tools.html\">": "pilot-map.html\">",
        "Twelve calculators, one per stage": "The chain on one illustrated map",
        "Move a slider, see the answer: the same formulas as each stage's Python code, on your own numbers.":
            "A fictional pilot woreda with a layer for each stage: suitability, water, clusters, stores, alerts, roads and the market.",
    }
    for a, b in rep.items():
        if a not in header:
            raise ValueError(f"header of tools.html changed, cannot find: {a[:40]}")
        header = header.replace(a, b)
    desc_start = header.index('<meta name="description" content="') + len('<meta name="description" content="')
    desc_end = header.index('">', desc_start)
    header = header[:desc_start] + ("An illustrated, interactive map of a fictional pilot woreda showing where each of the twelve stages of the "
                                    "Amhara Integrated Agriculture Ecosystem happens on the ground.") + header[desc_end:]
    css = '''<style>
    .map-wrap { display: flex; flex-direction: column; gap: 12px; margin-top: 14px; }
    .map-wrap .layers { order: 0; } .map-wrap .pan-hint { order: 1; } .map-wrap .map-card { order: 2; }
    .map-card { position: relative; background: #eef1e6; border: 1px solid var(--border); border-radius: 18px; overflow: hidden; box-shadow: 0 10px 34px rgba(31,42,32,.10); }
    .map-card svg { display: block; width: 100%; height: auto; }
    :root[data-theme="dark"] .map-card svg { filter: brightness(.9) saturate(.95); }
    @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .map-card svg { filter: brightness(.9) saturate(.95); } }
    .map-tip { position: absolute; pointer-events: none; max-width: 300px; background: #1f2a20; color: #fff; font-size: 13px; line-height: 1.45;
      padding: 8px 11px; border-radius: 9px; box-shadow: 0 8px 22px rgba(0,0,0,.25); opacity: 0; transform: translateY(4px); transition: opacity .12s ease, transform .12s ease; z-index: 3; }
    .map-tip.on { opacity: 1; transform: none; }
    .layers { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    .layers h2 { font-size: 14px; margin: 0 4px 0 0; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
    .layers label { display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px 6px 9px; border-radius: 999px; border: 1px solid var(--border);
      background: var(--surface); cursor: pointer; font-size: 14px; font-weight: 600; user-select: none; }
    .layers label:has(input:checked) { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, var(--surface)); }
    .layers label:has(input:focus-visible) { outline: 3px solid var(--accent); outline-offset: 2px; }
    .layers input { width: 16px; height: 16px; margin: 0; accent-color: var(--accent); }
    .layers small { color: var(--muted); font-weight: 700; font-size: 11.5px; }
    .layers .row { display: inline-flex; gap: 6px; margin-left: auto; }
    .layers .row button { font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; }
    .pan-hint { display: none; color: var(--muted); font-size: 13px; margin: 0; }
    @media (max-width: 760px) {
      .map-card { overflow-x: auto; overscroll-behavior-x: contain; }
      .map-card svg { width: 760px; max-width: none; }
      .layers label { font-size: 13px; padding: 4px 10px 4px 8px; }
      .layers h2 { width: 100%; }
      .pan-hint { display: block; }
    }
    .legend { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 12px 2px 0; font-size: 13px; color: var(--muted); }
    .legend i { display: inline-block; width: 14px; height: 14px; border-radius: 4px; vertical-align: -2px; margin-right: 5px; }
    .legend .ln { width: 22px; height: 0; border-radius: 0; border-top: 4px solid; vertical-align: 3px; }
    .walk { counter-reset: walk; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 10px; }
    .walk li { list-style: none; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px 12px 50px; position: relative; font-size: 14.5px; }
    .walk li::before { counter-increment: walk; content: counter(walk); position: absolute; left: 14px; top: 12px; width: 26px; height: 26px; border-radius: 50%;
      display: grid; place-items: center; font-weight: 800; font-size: 13px; background: var(--accent); color: var(--accent-contrast); }
    .walk a { font-weight: 700; }
  </style>'''
    s0, s1 = header.index("<style>"), header.index("</style>") + len("</style>")
    header = header[:s0] + css + header[s1:]
    boxes = "\n".join(
        f'      <label title="{E(hint)}"><input type="checkbox" data-layer="{k}" checked>{E(name)} <small>{n}</small></label>'
        for k, n, name, hint in LAYERS)
    rows = "\n".join(f'<tr><td>{k["id"]}</td><td>{k["cls"]}</td><td>{E(k["limit"])}</td><td>{k["cluster"]}</td><td class="num">{k["hh"]}</td></tr>' for k in keb)
    body = f'''<main class="container">
  <section class="hero" style="padding-bottom:4px">
    <span class="eyebrow">Illustrated map</span>
    <h1>The chain on one map</h1>
    <p class="lead">Twelve stages, one landscape. This fictional woreda shows where each stage works on the ground: which kebeles suit teff, where the water is, how clusters, stores, roads and the market connect. Turn layers on and off, and hover any feature for what it does.</p>
  </section>

  <div class="map-wrap">
    <p class="pan-hint">Swipe sideways to pan the map; tap a feature for its role.</p>
    <div class="map-card" id="map-card" tabindex="0" role="region" aria-label="Map of the fictional pilot woreda; scroll sideways on small screens">
{svg}
      <div class="map-tip" id="map-tip" role="status" aria-live="polite"></div>
    </div>
    <aside class="layers" aria-label="Map layers">
      <h2>Layers</h2>
{boxes}
      <div class="row"><button type="button" data-all="1">All on</button><button type="button" data-all="0">All off</button></div>
    </aside>
  </div>
  <div class="legend" aria-label="Legend">
    <span><i style="background:#1f7a45"></i>S1 highly suitable</span><span><i style="background:#7fb069"></i>S2 moderately</span>
    <span><i style="background:#e3a64b"></i>S3 marginal</span><span><i style="background:#c4553b"></i>N not suitable</span>
    <span><i class="ln" style="border-color:#5a5a5a"></i>asphalt</span><span><i class="ln" style="border-color:#b9a27a"></i>gravel</span>
    <span><i class="ln" style="border-color:#9a6b3a;border-top-style:dashed"></i>earth road (closes in the rains)</span>
    <span><i class="ln" style="border-color:#2a78d6;border-top-style:dotted"></i>season rainfall</span>
  </div>

  <section style="padding-top:34px">
    <h2>Read the map as one season</h2>
    <ol class="walk">
      <li>The <a href="/stages/05-market-intelligence/">buyer in the market town</a> signs a price-band contract before planting.</li>
      <li><a href="/stages/01-land-intelligence/">Suitability</a>, <a href="/stages/02-water-resources/">water</a> and <a href="/stages/03-climate-intelligence/">rainfall</a> say which kebeles can grow it, and when.</li>
      <li>The <a href="/stages/04-crop-planning/">planner</a> sets hectares per cluster A, B and C.</li>
      <li><a href="/stages/06-input-coordination/">Cooperative stores</a> receive seed and fertilizer ordered back from planting day.</li>
      <li><a href="/stages/07-farm-production/">Agents</a> follow the field calendar; <a href="/stages/08-monitoring-risk/">satellites</a> flag plots that fall behind.</li>
      <li>Harvest lots go to the <a href="/stages/09-harvest-postharvest/">collection centres</a> to be <a href="/stages/10-storage-aggregation/">dried, graded and stored</a>.</li>
      <li><a href="/stages/11-logistics-transport/">Trucks</a> collect before the earth roads close and deliver to the town.</li>
      <li>The <a href="/stages/12-market-distribution/">settlement</a> pays households, and the results feed next season's plan.</li>
    </ol>
  </section>

  <section style="padding-top:26px">
    <h2>Kebeles on the map</h2>
    <p class="section-intro">The same information as the map's suitability and cluster layers, as a table. All values are invented.</p>
    <div class="table-wrap"><table><thead><tr><th>Kebele</th><th>Teff class</th><th>Main limit</th><th>Cluster</th><th class="num">Households (approx.)</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  </section>
</main>

<footer class="footer-v2">
  <div class="container"><div class="fine"><span>Fictional woreda: every place, value and shape on this map is invented. No personal farmer data.</span><span><a href="/findings.html">Findings</a> · <a href="/tools.html">Calculators</a> · <a href="/">Back to the hub</a></span></div></div>
</footer>
<script>
(function () {{
  "use strict";
  try {{
    var svg = document.getElementById("pmap"), card = document.getElementById("map-card"), tipEl = document.getElementById("map-tip");
    function setLayer(name, on) {{
      svg.querySelectorAll('[data-layer="' + name + '"]').forEach(function (g) {{ g.style.display = on ? "" : "none"; }});
      svg.querySelectorAll('[data-off="' + name + '"]').forEach(function (g) {{ g.style.display = on ? "none" : ""; }});
    }}
    var boxes = document.querySelectorAll(".layers input[data-layer]");
    boxes.forEach(function (b) {{ b.addEventListener("change", function () {{ setLayer(b.dataset.layer, b.checked); }}); }});
    document.querySelectorAll(".layers [data-all]").forEach(function (btn) {{ btn.addEventListener("click", function () {{
      boxes.forEach(function (b) {{ b.checked = btn.dataset.all === "1"; setLayer(b.dataset.layer, b.checked); }}); }}); }});
    function show(el, x, y) {{
      tipEl.textContent = el.getAttribute("data-tip"); tipEl.classList.add("on");
      var r = card.getBoundingClientRect(), w = tipEl.offsetWidth, h = tipEl.offsetHeight;
      var sl = card.scrollLeft, vw = card.clientWidth;     // the card scrolls sideways on phones
      tipEl.style.left = (sl + Math.max(8, Math.min(vw - w - 8, x - r.left + 14))) + "px";
      tipEl.style.top = Math.max(8, Math.min(r.height - h - 8, y - r.top + 14)) + "px";
    }}
    function hide() {{ tipEl.classList.remove("on"); }}
    svg.addEventListener("pointermove", function (e) {{ var el = e.target.closest("[data-tip]"); if (el) show(el, e.clientX, e.clientY); else hide(); }});
    svg.addEventListener("pointerleave", hide);
    svg.addEventListener("focusin", function (e) {{ var el = e.target.closest("[data-tip]"); if (!el) return; var b = el.getBoundingClientRect(); show(el, b.left + b.width / 2, b.top + b.height / 2); }});
    svg.addEventListener("focusout", hide);
  }} catch (e) {{ if (window.console) console.error("[pilot-map] interaction failed", e); }}
}})();
</script>
</body>
</html>
'''
    return header + body


def main() -> int:
    svg, keb = build_svg()
    (ROOT / "pilot-map.html").write_text(build_page(svg, keb), encoding="utf-8")
    (ROOT / "assets" / "img" / "pilot-map.svg").write_text(svg + "\n", encoding="utf-8")   # static copy for the hub teaser
    print(f"[OK] pilot-map.html ({len(keb)} kebeles)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # debugging block: say what failed and where
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""
Generate the twelve stage illustrations (assets/img/stages/<slug>.svg) in one consistent style.

Each scene is 640 x 400, built from shared primitives (sky, hills, fields, tukul, tree, sacks, truck ...)
so colours and line weights match the hub landscape. Re-run after editing a scene:

    python3 tools/make_stage_art.py            # writes all 12
    python3 tools/make_stage_art.py 04 08      # only these stages
    python3 tools/make_stage_art.py panorama   # only the 12-stage panorama strip
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "img" / "stages"
W, H = 640, 400

C = dict(sky1="#bfe0ef", sky2="#f4f1e2", hill_far="#b9cbb1", hill_mid="#8fb27c", ground="#b3cc95", ground2="#cfdcae",
         teff="#dcb85e", wheat="#a9c766", maize="#6f9b48", fallow="#c49a68", water="#7fb5d1", water_d="#5f9fc0",
         wall="#d8c2a0", roof="#8a6d3b", wood="#6b5428", tree="#557f43", ink="#1f2a20", muted="#5d665e",
         plan="#8a6d3b", produce="#3f6b34", move="#2f5d8a", sell="#9a4a28", gold="#f2c14e", white="#ffffff", stone="#cfc6b6")


# ------------------------------------------------------------------ primitives
def sky(top=C["sky1"], bottom=C["sky2"], sun=(560, 70), clouds=((140, 70), (330, 52))) -> str:
    s = (f'<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
         f'<stop offset="1" stop-color="{bottom}"/></linearGradient></defs><rect width="{W}" height="{H}" fill="url(#sky)"/>')
    if sun:
        s += f'<circle cx="{sun[0]}" cy="{sun[1]}" r="58" fill="#ffe7a3" opacity=".5"/><circle cx="{sun[0]}" cy="{sun[1]}" r="30" fill="{C["gold"]}"/>'
    for x, y in clouds:
        s += cloud(x, y)
    return s


def cloud(x, y, k=1.0, fill="#ffffff", op=.95) -> str:
    return (f'<g fill="{fill}" opacity="{op}"><ellipse cx="{x}" cy="{y}" rx="{46 * k}" ry="{16 * k}"/>'
            f'<ellipse cx="{x + 26 * k}" cy="{y - 10 * k}" rx="{30 * k}" ry="{20 * k}"/><ellipse cx="{x - 24 * k}" cy="{y - 4 * k}" rx="{22 * k}" ry="{14 * k}"/></g>')


def ambas(y=170, fill=C["hill_far"]) -> str:
    return (f'<path d="M0 {y + 30} L40 {y + 8} L110 {y + 8} L150 {y - 16} L250 {y - 16} L290 {y + 10} L380 {y + 14} L430 {y - 22} '
            f'L560 {y - 22} L600 {y + 6} L640 {y + 4} L640 {H} L0 {H} Z" fill="{fill}"/>')


def hills(y=230, fill=C["hill_mid"]) -> str:
    return (f'<path d="M0 {y} C110 {y - 40} 220 {y - 44} 330 {y - 18} C430 {y + 6} 520 {y - 34} 640 {y - 20} L640 {H} L0 {H} Z" fill="{fill}"/>')


def ground(y=290, fill=C["ground"]) -> str:
    return f'<path d="M0 {y} C160 {y - 12} 320 {y - 14} 480 {y - 8} C560 {y - 6} 600 {y - 4} 640 {y} L640 {H} L0 {H} Z" fill="{fill}"/>'


def field(points, fill, stripe=None, angle=0) -> str:
    pts = " ".join(f"{x},{y}" for x, y in points)
    out = f'<polygon points="{pts}" fill="{fill}" stroke="#f7f0dc" stroke-width="3"/>'
    if stripe:
        xs = [p[0] for p in points]; ys = [p[1] for p in points]
        cid = f"c{abs(hash((pts, stripe))) % 10**8}"
        out += f'<clipPath id="{cid}"><polygon points="{pts}"/></clipPath><g clip-path="url(#{cid})" stroke="{stripe}" stroke-width="2.4">'
        for yy in range(min(ys) - 40, max(ys) + 40, 9):
            out += f'<line x1="{min(xs) - 40}" y1="{yy}" x2="{max(xs) + 40}" y2="{yy + angle}"/>'
        out += "</g>"
    return out


def tukul(x, y, k=1.0) -> str:
    return (f'<g transform="translate({x} {y}) scale({k})"><rect x="-16" y="-8" width="32" height="24" rx="3" fill="{C["wall"]}"/>'
            f'<path d="M-25 -5 L0 -32 L25 -5 Z" fill="{C["roof"]}"/><rect x="-5" y="4" width="10" height="12" fill="{C["wood"]}"/></g>')


def tree(x, y, k=1.0) -> str:
    return (f'<g transform="translate({x} {y}) scale({k})"><path d="M0 0 v-24" stroke="{C["wood"]}" stroke-width="4"/>'
            f'<ellipse cx="0" cy="-28" rx="30" ry="9" fill="{C["tree"]}"/></g>')


def sack(x, y, k=1.0, fill="#e9dcc2", label="", stroke="#a9843a") -> str:
    t = f'<text x="0" y="6" text-anchor="middle" font-size="9" font-weight="700" fill="{C["wood"]}">{label}</text>' if label else ""
    return (f'<g transform="translate({x} {y}) scale({k})"><path d="M-14 -18 h28 l4 6 c4 10 4 24 0 30 h-36 c-4 -6 -4 -20 0 -30 z" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/><path d="M-14 -18 q14 -8 28 0" fill="none" stroke="{stroke}" stroke-width="1.5"/>{t}</g>')


def truck(x, y, k=1.0, color=C["move"], load=None) -> str:
    cargo = ""
    if load:
        cargo = "".join(f'<rect x="{4 + i * 17}" y="-10" width="15" height="12" rx="3" fill="{load}" stroke="#a9843a"/>' for i in range(3))
    return (f'<g transform="translate({x} {y}) scale({k})">{cargo}<rect x="0" y="0" width="58" height="30" rx="3" fill="{color}"/>'
            f'<path d="M58 8 h18 l12 12 v10 h-30 z" fill="#3f78ad"/><rect x="64" y="11" width="10" height="8" fill="#cfe6f5"/>'
            f'<circle cx="16" cy="32" r="7" fill="#263238"/><circle cx="72" cy="32" r="7" fill="#263238"/>'
            f'<circle cx="16" cy="32" r="2.5" fill="#cfd8dc"/><circle cx="72" cy="32" r="2.5" fill="#cfd8dc"/></g>')


def person(x, y, k=1.0, shirt=C["produce"], skin="#7a5236") -> str:
    return (f'<g transform="translate({x} {y}) scale({k})"><circle cx="0" cy="-34" r="6" fill="{skin}"/>'
            f'<path d="M-8 -26 h16 l3 18 h-22 z" fill="{shirt}"/><path d="M-6 -8 l-2 16 M6 -8 l2 16" stroke="{C["ink"]}" stroke-width="3" stroke-linecap="round"/></g>')


def badge(x, y, text, color) -> str:
    w = 8 + 7.2 * len(text)
    return (f'<g transform="translate({x} {y})"><rect x="0" y="-14" width="{w}" height="22" rx="11" fill="{color}"/>'
            f'<text x="{w / 2}" y="2" text-anchor="middle" font-size="11.5" font-weight="700" fill="#fff">{text}</text></g>')


def frame(body: str, title: str, desc: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d" '
            f'font-family="Helvetica, Arial, sans-serif"><title id="t">{title}</title><desc id="d">{desc}</desc>{body}</svg>\n')


# ------------------------------------------------------------------ scenes
def s01():
    b = sky(clouds=((120, 60),)) + ambas() + hills(220)
    # terraces on the hillside
    b += "".join(f'<path d="M{-10 + i * 6} {205 + i * 15} C120 {182 + i * 15} 230 {186 + i * 15} 330 {205 + i * 15}" fill="none" stroke="#b7cf9f" stroke-width="3"/>' for i in range(6))
    b += ground(300)
    # suitability grid
    cls = ["#1a9641", "#a6d96a", "#a6d96a", "#fdae61", "#1a9641", "#1a9641", "#a6d96a", "#d7191c", "#1a9641", "#a6d96a", "#fdae61", "#fdae61"]
    for i, col in enumerate(cls):
        x, y = 370 + (i % 4) * 46, 240 + (i // 4) * 34
        b += f'<rect x="{x}" y="{y}" width="42" height="30" rx="4" fill="{col}" opacity=".85" stroke="#fff" stroke-width="2"/>'
    b += '<g font-size="11" font-weight="700" fill="#fff"><text x="382" y="260">S1</text><text x="428" y="260">S2</text><text x="566" y="294">N</text><text x="508" y="328">S3</text></g>'
    # soil profile cutaway
    for i, (col, lab) in enumerate([("#5b4a2a", "topsoil"), ("#8a6d3b", "subsoil"), ("#b59a6a", "parent rock")]):
        b += f'<rect x="40" y="{300 + i * 30}" width="140" height="30" fill="{col}"/><text x="190" y="{320 + i * 30}" font-size="12" fill="{C["ink"]}">{lab}</text>'
    b += '<g stroke="#e9dcc2" stroke-width="2"><circle cx="70" cy="315" r="3"/><circle cx="120" cy="322" r="2"/><circle cx="150" cy="345" r="3"/></g>'
    # survey pin
    b += f'<g transform="translate(250 170)"><path d="M0 -36 a16 16 0 0 1 16 16 c0 14 -16 30 -16 30 s-16 -16 -16 -30 a16 16 0 0 1 16 -16z" fill="{C["plan"]}"/><circle cx="0" cy="-20" r="6" fill="#fff"/></g>'
    b += badge(370, 380, "plot x crop -> S1 / S2 / S3 / N", C["plan"])
    return frame(b, "Land intelligence and suitability", "Terraced hillside, a soil profile cutaway, a survey pin and a grid of plots coloured by suitability class.")


def s02():
    b = sky(clouds=((160, 60), (420, 44))) + ambas() + hills(222) + ground(296)
    b += f'<path d="M420 160 C400 210 330 230 300 262 C270 294 210 310 120 330 L0 352" fill="none" stroke="{C["water"]}" stroke-width="16" stroke-linecap="round"/>'
    b += f'<path d="M420 160 C400 210 330 230 300 262 C270 294 210 310 120 330 L0 352" fill="none" stroke="#e6f4fa" stroke-width="3" stroke-dasharray="12 16"/>'
    # weir and canal
    b += f'<rect x="282" y="250" width="34" height="16" rx="3" fill="{C["stone"]}" stroke="#8a8173" stroke-width="2" transform="rotate(-35 299 258)"/>'
    b += f'<path d="M300 262 C360 286 430 300 520 304" fill="none" stroke="{C["water"]}" stroke-width="6" stroke-dasharray="10 6"/>'
    b += field([(430, 300), (560, 296), (600, 360), (440, 372)], C["wheat"], "#93b354")
    b += field([(560, 296), (640, 300), (640, 360), (600, 360)], "#7fb36a", "#a7cf8c")
    # well with pump
    b += f'<g transform="translate(170 300)"><ellipse cx="0" cy="0" rx="20" ry="7" fill="#3c6e8f"/><rect x="-20" y="0" width="40" height="18" fill="{C["stone"]}"/><path d="M-12 -2 v-26 h24 v8" stroke="{C["ink"]}" stroke-width="3" fill="none"/></g>'
    # monthly water bars inset
    vals = [5, 4, 3, 3, 4, 8, 10, 10, 9, 7, 6, 5]
    b += f'<rect x="440" y="96" width="176" height="96" rx="10" fill="#ffffff" opacity=".9"/>'
    for i, v in enumerate(vals):
        b += f'<rect x="{452 + i * 13.5}" y="{180 - v * 7}" width="10" height="{v * 7}" rx="2" fill="{C["water_d"] if i in (1, 2, 3) else C["water"]}"/>'
    b += f'<text x="452" y="114" font-size="11" font-weight="700" fill="{C["ink"]}">supply by month</text><text x="452" y="128" font-size="10" fill="{C["muted"]}">lean months decide the area</text>'
    return frame(b, "Water resource assessment", "A river with a diversion weir and canal irrigating fields, a hand-dug well with a pump, and a small chart of water supply by month.")


def s03():
    b = sky(top="#a9cfe3", sun=(120, 80), clouds=()) + cloud(380, 90, 1.5, "#b9c7d3", 1) + cloud(250, 70, 1.0)
    b += '<g stroke="#7fa7c4" stroke-width="3" stroke-linecap="round">' + "".join(f'<line x1="{330 + i * 18}" y1="{125 + (i % 2) * 6}" x2="{322 + i * 18}" y2="{148 + (i % 2) * 6}"/>' for i in range(7)) + "</g>"
    b += ambas(200) + hills(250) + ground(310)
    # rain gauge and thermometer
    b += f'<g transform="translate(520 230)"><rect x="-14" y="-60" width="28" height="80" rx="4" fill="#ffffff" stroke="{C["move"]}" stroke-width="2"/><rect x="-12" y="-20" width="24" height="38" fill="{C["water"]}"/><path d="M-14 -40 h8 M-14 -20 h8 M-14 0 h8" stroke="{C["move"]}" stroke-width="2"/><rect x="-4" y="20" width="8" height="40" fill="{C["wood"]}"/></g>'
    b += f'<g transform="translate(580 230)"><rect x="-6" y="-56" width="12" height="70" rx="6" fill="#ffffff" stroke="{C["sell"]}" stroke-width="2"/><rect x="-2" y="-30" width="4" height="44" fill="{C["sell"]}"/><circle cx="0" cy="18" r="10" fill="{C["sell"]}"/></g>'
    # season band
    seasons = [("Bega", "#e6c27a", 0, 1), ("Belg", "#9bc7a0", 1, 5), ("Kiremt", "#7fb5d1", 5, 9), ("Bega", "#e6c27a", 9, 12)]
    for name, col, a, z in seasons:
        b += f'<rect x="{40 + a * 46}" y="342" width="{(z - a) * 46 - 4}" height="34" rx="8" fill="{col}"/>'
        if z - a > 1:
            b += f'<text x="{40 + (a + z) / 2 * 46 - 2}" y="364" text-anchor="middle" font-size="12" font-weight="700" fill="{C["ink"]}">{name}</text>'
    b += "".join(f'<text x="{40 + (i + .5) * 46 - 2}" y="392" text-anchor="middle" font-size="10" fill="{C["muted"]}">{m}</text>' for i, m in enumerate("JFMAMJJASOND"))
    b += f'<path d="M{40 + 5.3 * 46} 336 v-14" stroke="{C["ink"]}" stroke-width="2"/><text x="{40 + 5.3 * 46}" y="316" text-anchor="middle" font-size="11" font-weight="700" fill="{C["ink"]}">onset</text>'
    return frame(b, "Climate and seasonal intelligence", "Sun and rain clouds over highlands, a rain gauge and a thermometer, and a band showing the Bega, Belg and Kiremt seasons through the year with the onset of the rains.")


def s04():
    b = sky(clouds=((150, 60),)) + ambas(190) + hills(240) + ground(300)
    b += field([(40, 300), (200, 292), (220, 350), (40, 362)], C["teff"], "#c9a14a")
    b += field([(200, 292), (330, 290), (350, 346), (220, 350)], C["maize"], "#5d863c")
    b += field([(40, 362), (220, 350), (230, 400), (40, 400)], C["wheat"], "#93b354")
    b += field([(220, 350), (350, 346), (360, 400), (230, 400)], C["teff"], "#c9a14a")
    # planning board
    b += f'<g transform="translate(400 120)"><rect x="0" y="0" width="210" height="190" rx="12" fill="#ffffff" stroke="{C["plan"]}" stroke-width="3"/>'
    b += f'<text x="16" y="28" font-size="14" font-weight="700" fill="{C["ink"]}">Seasonal plan</text>'
    rows = [("teff", C["teff"], 0.62), ("wheat", C["wheat"], 0.48), ("maize", C["maize"], 0.36), ("onion", "#7fb36a", 0.22)]
    for i, (n, col, v) in enumerate(rows):
        b += f'<text x="16" y="{62 + i * 30}" font-size="12" fill="{C["muted"]}">{n}</text><rect x="64" y="{50 + i * 30}" width="{130 * v / .62:.0f}" height="16" rx="4" fill="{col}"/>'
    b += f'<path d="M16 172 h180" stroke="{C["muted"]}" stroke-dasharray="4 4"/><text x="16" y="186" font-size="10.5" fill="{C["sell"]}">water in March: 50 birr per extra m3</text></g>'
    b += f'<path d="M330 250 C360 230 380 220 398 210" fill="none" stroke="{C["plan"]}" stroke-width="2.5" stroke-dasharray="6 5"/>'
    return frame(b, "Crop selection and production planning", "A patchwork of teff, maize and wheat fields beside a seasonal plan board with bars for each crop and a note on the value of extra water.")


def s05():
    b = sky(clouds=((300, 54),)) + ambas(210) + ground(270, C["ground2"])
    # market stalls
    for i, (x, col) in enumerate([(40, C["sell"]), (210, C["plan"])]):
        b += f'<g transform="translate({x} 250)"><rect x="0" y="0" width="150" height="70" fill="#f5e1d7"/><path d="M-8 0 h166 l-12 -28 h-142 z" fill="{col}"/>'
        b += "".join(f'<rect x="{6 + j * 30}" y="-28" width="14" height="28" fill="#ffffff" opacity=".25"/>' for j in range(5))
        b += f'<g fill="{C["teff"]}"><circle cx="30" cy="44" r="12"/><circle cx="54" cy="48" r="10"/></g><g fill="{C["wheat"]}"><circle cx="96" cy="44" r="12"/><circle cx="120" cy="48" r="10"/></g></g>'
    b += person(130, 372, 1.1, C["sell"]) + person(300, 372, 1.1, C["move"])
    # price board
    b += f'<g transform="translate(400 90)"><rect x="0" y="0" width="210" height="160" rx="12" fill="#ffffff" stroke="{C["sell"]}" stroke-width="3"/>'
    b += f'<text x="14" y="26" font-size="13" font-weight="700" fill="{C["ink"]}">wheat price, birr/t</text>'
    pts = [(20, 120), (40, 110), (60, 116), (80, 100), (100, 104), (120, 90), (140, 92)]
    b += '<polyline points="' + " ".join(f"{x},{y}" for x, y in pts) + f'" fill="none" stroke="{C["move"]}" stroke-width="3"/>'
    b += f'<path d="M140 92 L190 72 L190 118 Z" fill="{C["sell"]}" opacity=".18"/><path d="M140 92 L190 94" stroke="{C["sell"]}" stroke-width="3" stroke-dasharray="6 4"/>'
    b += f'<path d="M150 60 h44 M150 132 h44" stroke="{C["ink"]}" stroke-dasharray="3 3"/><text x="152" y="54" font-size="9.5" fill="{C["muted"]}">ceiling</text><text x="152" y="146" font-size="9.5" fill="{C["muted"]}">floor</text></g>'
    b += sack(470, 340, 1.4, label="900 t") + sack(530, 344, 1.2) + sack(580, 348, 1.0)
    return frame(b, "Market intelligence and demand forecasting", "Market stalls with grain, a buyer and a seller, a price board with a forecast band between floor and ceiling, and grain sacks for a contracted volume.")


def s06():
    b = sky(clouds=((140, 56), (360, 46))) + ambas(200) + ground(280)
    # cooperative store
    b += f'<g transform="translate(330 200)"><path d="M0 100 V30 L110 -10 L220 30 V100 Z" fill="#e9dcc2" stroke="{C["plan"]}" stroke-width="2.5"/>'
    b += f'<path d="M-10 32 L110 -18 L230 32" fill="none" stroke="{C["sell"]}" stroke-width="8" stroke-linecap="round"/><rect x="84" y="46" width="52" height="54" fill="{C["plan"]}"/>'
    b += f'<text x="110" y="24" text-anchor="middle" font-size="12" font-weight="700" fill="{C["wood"]}">cooperative store</text></g>'
    b += sack(300, 334, 1.3, "#e9dcc2", "SEED") + sack(260, 340, 1.3, "#f1f1f1", "NPS", "#8a8173") + sack(222, 346, 1.2, "#f1f1f1", "UREA", "#8a8173") + sack(560, 340, 1.2, "#efe7d6", "LIME", "#8a8173")
    b += truck(40, 300, 1.2, load="#e9dcc2")
    # calendar with check
    b += f'<g transform="translate(470 74)"><rect x="0" y="0" width="130" height="104" rx="10" fill="#ffffff" stroke="{C["produce"]}" stroke-width="3"/><rect x="0" y="0" width="130" height="26" rx="10" fill="{C["produce"]}"/>'
    b += f'<text x="65" y="18" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">order by</text>'
    b += "".join(f'<rect x="{12 + (i % 5) * 22}" y="{36 + (i // 5) * 20}" width="16" height="14" rx="3" fill="{C["ground2"]}"/>' for i in range(15))
    b += f'<rect x="56" y="56" width="16" height="14" rx="3" fill="{C["sell"]}"/><path d="M84 78 l10 10 l22 -26" fill="none" stroke="{C["produce"]}" stroke-width="5" stroke-linecap="round"/></g>'
    return frame(b, "Input and resource coordination", "A truck delivering sacks of seed, NPS, urea and lime to a cooperative store, with a calendar showing an order-by date ticked off.")


def s07():
    b = sky(clouds=((160, 60), (420, 50))) + ambas(196) + hills(240) + ground(286)
    # rows of seedlings in perspective
    for i in range(7):
        y = 300 + i * 14
        b += f'<path d="M{20 + i * 4} {y} L{620 - i * 4} {y - 6}" stroke="#a88b5e" stroke-width="2"/>'
        b += "".join(f'<path d="M{40 + j * 44 + i * 3} {y - 1} q-5 -9 -1 -14 M{40 + j * 44 + i * 3} {y - 1} q6 -8 2 -14" stroke="{C["produce"]}" stroke-width="2.4" fill="none"/>' for j in range(13) if (j + i) % 2 == 0)
    # ox plough team
    b += f'<g transform="translate(360 268)"><ellipse cx="0" cy="0" rx="34" ry="14" fill="#6b5428"/><circle cx="34" cy="-8" r="9" fill="#6b5428"/><path d="M28 -16 l-6 -8 M40 -16 l6 -8" stroke="#e9dcc2" stroke-width="3"/>'
    b += '<path d="M-22 10 v14 M-8 12 v14 M10 12 v14 M24 10 v14" stroke="#4a3a1e" stroke-width="5"/></g>'
    b += f'<path d="M320 262 L250 280" stroke="{C["wood"]}" stroke-width="4"/>' + person(240, 300, 1.1, C["produce"])
    # development agent with tablet
    b += person(520, 330, 1.2, C["move"]) + f'<rect x="532" y="282" width="20" height="26" rx="3" fill="#263238" transform="rotate(12 542 295)"/>'
    b += badge(40, 380, "planted on time: 91%", C["produce"])
    return frame(b, "Farm implementation and production", "Rows of seedlings, a farmer ploughing with an ox team, and a development agent with a tablet recording field operations.")


def s08():
    b = sky(top="#9cc8df", sun=None, clouds=((520, 70),)) + ambas(220) + ground(270)
    # NDVI grid of plots
    cols = ["#1a9641", "#1a9641", "#a6d96a", "#1a9641", "#a6d96a", "#1a9641", "#d7191c", "#fdae61", "#1a9641", "#a6d96a", "#1a9641", "#1a9641",
            "#a6d96a", "#1a9641", "#fdae61", "#1a9641", "#1a9641", "#a6d96a"]
    for i, col in enumerate(cols):
        x, y = 140 + (i % 6) * 64 - (i // 6) * 18, 290 + (i // 6) * 34
        b += f'<path d="M{x} {y} h60 l-6 30 h-60 z" fill="{col}" opacity=".85" stroke="#fff" stroke-width="2"/>'
    # satellite and beam
    b += f'<path d="M150 70 L120 290 L520 290 Z" fill="#8ab8e6" opacity=".25"/>'
    b += (f'<g transform="translate(150 70) rotate(-18)"><rect x="-12" y="-12" width="24" height="24" rx="4" fill="#5d6d7e"/>'
          f'<rect x="-64" y="-10" width="42" height="20" rx="2" fill="{C["move"]}"/><rect x="22" y="-10" width="42" height="20" rx="2" fill="{C["move"]}"/>'
          f'<path d="M-64 0h42M22 0h42M-43-10v20M43-10v20" stroke="#8ab8e6"/><path d="M-22 0h10M12 0h10" stroke="#5d6d7e" stroke-width="4"/></g>')
    # alert marker
    b += f'<g transform="translate(358 330)"><circle r="20" fill="none" stroke="{C["sell"]}" stroke-width="3"/><circle r="30" fill="none" stroke="{C["sell"]}" stroke-width="2" opacity=".5"/></g>'
    b += badge(390, 286, "warning: z -4.9", C["sell"])
    # growth curve inset
    b += f'<g transform="translate(430 96)"><rect x="0" y="0" width="186" height="104" rx="10" fill="#ffffff" opacity=".92"/>'
    b += f'<path d="M14 88 C50 86 64 30 96 26 C128 24 140 70 172 84" fill="none" stroke="{C["produce"]}" stroke-width="3"/>'
    b += f'<path d="M14 88 C50 86 64 34 92 46 C110 54 130 70 172 86" fill="none" stroke="{C["sell"]}" stroke-width="3" stroke-dasharray="5 4"/>'
    b += f'<text x="12" y="16" font-size="10.5" font-weight="700" fill="{C["ink"]}">NDVI: expected vs plot</text></g>'
    return frame(b, "Monitoring, forecasting and risk", "A satellite scanning a grid of plots coloured by vegetation health, an alert circle on a stressed plot, and a growth curve comparing expected and observed greenness.")


def s09():
    b = sky(top="#cfe2ea", sun=(540, 76), clouds=((200, 56),)) + ambas(196) + ground(250, "#d9c27a")
    b += "".join(f'<path d="M0 {260 + i * 12} C200 {254 + i * 12} 440 {256 + i * 12} 640 {262 + i * 12}" stroke="#c9a14a" stroke-width="2" fill="none"/>' for i in range(4))
    # teff stacks
    b += "".join(f'<path d="M{x} 300 q22 -52 44 0 z" fill="{C["teff"]}" stroke="#a9843a" stroke-width="2"/>' for x in (40, 96, 150))
    # tarpaulin with grain and thresher
    b += f'<path d="M210 330 L380 318 L420 372 L230 390 Z" fill="#2f5d8a" opacity=".85"/><ellipse cx="315" cy="352" rx="62" ry="16" fill="{C["teff"]}"/>'
    b += (f'<g transform="translate(430 268)"><rect x="0" y="0" width="90" height="48" rx="6" fill="{C["sell"]}"/><rect x="10" y="-22" width="40" height="24" fill="{C["sell"]}"/>'
          f'<path d="M90 16 l30 -10 v20" fill="#7a3a1e"/><circle cx="20" cy="54" r="10" fill="#263238"/><circle cx="72" cy="54" r="10" fill="#263238"/></g>')
    # lot-tagged bags
    for i, x in enumerate((470, 520, 570)):
        b += sack(x, 370, 1.15, "#efe7d6", f"LOT {i + 1}")
    b += person(190, 330, 1.1, C["move"])
    return frame(b, "Harvest and post-harvest management", "A golden field with teff stacks, grain on a tarpaulin, a thresher, and sacks tagged with lot numbers for traceability.")


def s10():
    b = sky(clouds=((160, 60),)) + ambas(206) + ground(290)
    b += (f'<g transform="translate(60 180)"><path d="M0 130 V40 L140 -10 L280 40 V130 Z" fill="#e9dcc2" stroke="{C["plan"]}" stroke-width="3"/>'
          f'<path d="M-12 42 L140 -20 L292 42" fill="none" stroke="{C["sell"]}" stroke-width="10" stroke-linecap="round"/><rect x="104" y="60" width="72" height="70" fill="{C["plan"]}"/>'
          f'<text x="140" y="32" text-anchor="middle" font-size="13" font-weight="700" fill="{C["wood"]}">collection centre</text></g>')
    b += "".join(f'<rect x="{360 + i * 36}" y="{170 - i * 6}" width="30" height="{140 + i * 6}" rx="15" fill="{C["stone"]}" stroke="#8a8173" stroke-width="2"/>' for i in range(2))
    # hermetic bag stack
    for r, n in enumerate((4, 3, 2)):
        for i in range(n):
            b += f'<rect x="{80 + r * 14 + i * 30}" y="{344 - r * 22}" width="28" height="20" rx="6" fill="#2f5d8a" stroke="#1f3f60"/>'
    # receipt
    b += (f'<g transform="translate(470 110) rotate(4)"><rect x="0" y="0" width="140" height="170" rx="8" fill="#ffffff" stroke="{C["move"]}" stroke-width="3"/>'
          f'<text x="14" y="26" font-size="12.5" font-weight="700" fill="{C["ink"]}">Warehouse receipt</text>'
          + "".join(f'<rect x="14" y="{42 + i * 18}" width="{110 - (i % 2) * 30}" height="8" rx="4" fill="{C["ground2"]}"/>' for i in range(5))
          + f'<text x="14" y="148" font-size="11" fill="{C["muted"]}">grade 1 · 9,468 kg</text><circle cx="112" cy="140" r="14" fill="none" stroke="{C["sell"]}" stroke-width="3"/></g>')
    b += badge(380, 380, "hermetic: +7% by May", C["move"])
    return frame(b, "Storage, processing and aggregation", "A collection centre with silos, a stack of hermetic grain bags and a warehouse receipt recording a graded lot.")


def s11():
    b = sky(clouds=((140, 58), (400, 46))) + ambas(186) + hills(230) + ground(300)
    road = "M0 380 C120 360 160 300 260 300 C360 300 380 250 470 240 C540 232 600 220 640 210"
    b += f'<path d="{road}" fill="none" stroke="#a89a85" stroke-width="30" stroke-linecap="round"/><path d="{road}" fill="none" stroke="#f3ead8" stroke-width="3" stroke-dasharray="14 12"/>'
    b += truck(210, 266, 1.0, load="#e9dcc2") + truck(470, 206, .8)
    # route network
    nodes = [(80, 250), (150, 210), (300, 190), (390, 160), (540, 150), (560, 290)]
    b += f'<path d="M80 250 L150 210 L300 190 L390 160 L540 150 M300 190 L560 290" stroke="{C["move"]}" stroke-width="2.5" stroke-dasharray="6 5" fill="none"/>'
    b += "".join(f'<circle cx="{x}" cy="{y}" r="7" fill="#fff" stroke="{C["move"]}" stroke-width="3"/>' for x, y in nodes)
    # rainy-season closure sign
    b += (f'<g transform="translate(570 290)"><path d="M0 -26 L24 16 H-24 Z" fill="{C["gold"]}" stroke="{C["ink"]}" stroke-width="2"/>'
          f'<text x="0" y="10" text-anchor="middle" font-size="18" font-weight="900" fill="{C["ink"]}">!</text><rect x="-2" y="16" width="4" height="24" fill="{C["ink"]}"/></g>')
    b += cloud(560, 236, .6, "#b9c7d3", 1)
    b += badge(40, 380, "consolidated routes: -14%", C["move"])
    return frame(b, "Logistics and transportation", "Trucks on a winding highland road, a dashed route network linking kebeles, and a warning sign for a road that closes in the rainy season.")


def s12():
    b = sky(clouds=((220, 56),)) + ambas(200) + ground(290)
    # mill / buyer building
    b += (f'<g transform="translate(420 170)"><rect x="0" y="30" width="170" height="110" fill="#f5e1d7" stroke="{C["sell"]}" stroke-width="3"/>'
          f'<path d="M-10 32 L85 -14 L180 32" fill="none" stroke="{C["sell"]}" stroke-width="9" stroke-linecap="round"/><rect x="66" y="80" width="38" height="60" fill="{C["sell"]}"/>'
          f'<text x="85" y="62" text-anchor="middle" font-size="12.5" font-weight="700" fill="{C["wood"]}">buyer</text></g>')
    b += tukul(80, 300, 1.2) + tukul(140, 318, 1.0) + tukul(196, 304, 1.1)
    # grain forward, money back
    b += f'<path d="M230 270 C300 230 360 230 410 250" fill="none" stroke="{C["plan"]}" stroke-width="4" marker-end="url(#ah)"/>'
    b += f'<path d="M410 300 C350 330 290 334 230 318" fill="none" stroke="{C["produce"]}" stroke-width="4" stroke-dasharray="8 6" marker-end="url(#ah2)"/>'
    b += (f'<defs><marker id="ah" markerUnits="userSpaceOnUse" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill="{C["plan"]}"/></marker>'
          f'<marker id="ah2" markerUnits="userSpaceOnUse" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill="{C["produce"]}"/></marker></defs>')
    b += f'<text x="320" y="228" text-anchor="middle" font-size="12" font-weight="700" fill="{C["plan"]}">grain and lots</text>'
    b += f'<text x="320" y="352" text-anchor="middle" font-size="12" font-weight="700" fill="{C["produce"]}">payments to households</text>'
    b += "".join(f'<g transform="translate({300 + i * 22} {300 + (i % 2) * 4})"><ellipse rx="10" ry="4" fill="{C["gold"]}" stroke="#a9843a"/></g>' for i in range(3))
    # learning loop badge
    b += f'<g transform="translate(560 84)"><circle r="40" fill="#ffffff" stroke="{C["produce"]}" stroke-width="4"/><path d="M-20 -6 a22 22 0 0 1 38 -10 M18 6 a22 22 0 0 1 -38 10" fill="none" stroke="{C["produce"]}" stroke-width="4" stroke-linecap="round"/><path d="M18 -26 l2 12 l-12 -2 M-18 26 l-2 -12 l12 2" fill="none" stroke="{C["produce"]}" stroke-width="4" stroke-linecap="round"/></g>'
    b += badge(40, 380, "income effect +8,795 birr", C["sell"])
    return frame(b, "Market distribution and customer network", "Grain flowing from homesteads to a buyer, payments flowing back to households, and a learning-loop symbol feeding lessons into the next season.")


PANO_LABELS = {1: "Land", 2: "Water", 3: "Climate", 4: "Planning", 5: "Market", 6: "Inputs", 7: "Field work", 8: "Monitoring",
               9: "Harvest", 10: "Storage", 11: "Logistics", 12: "Distribution"}


def panorama(stages) -> str:
    """One continuous 2400 x 360 strip walking through all twelve stages along a single road."""
    PW, PH, seg = 2400, 360, 200
    b = (f'<defs><linearGradient id="psky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["sky1"]}"/><stop offset="1" stop-color="{C["sky2"]}"/></linearGradient>'
         f'<marker id="pa" markerUnits="userSpaceOnUse" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill="{C["produce"]}"/></marker></defs>'
         f'<rect width="{PW}" height="{PH}" fill="url(#psky)"/>')
    # far ambas across the whole strip
    pts = "M0 170"
    for i in range(0, PW + 200, 200):
        pts += f" L{i + 30} 150 L{i + 90} 150 L{i + 120} 128 L{i + 170} 128 L{i + 200} 160"
    b += f'<path d="{pts} L{PW} {PH} L0 {PH} Z" fill="{C["hill_far"]}"/>'
    b += f'<path d="M0 214 C300 180 600 196 900 206 C1200 216 1500 182 1800 196 C2100 210 2250 190 2400 200 L2400 {PH} L0 {PH} Z" fill="{C["hill_mid"]}"/>'
    b += f'<path d="M0 252 C400 240 800 246 1200 250 C1600 254 2000 244 2400 250 L2400 {PH} L0 {PH} Z" fill="{C["ground"]}"/>'
    # the road that ties the chain together
    road = "M0 330 C300 318 600 330 900 322 C1200 314 1500 330 1800 322 C2100 314 2250 326 2400 320"
    b += f'<path d="{road}" fill="none" stroke="#a89a85" stroke-width="22"/><path d="{road}" fill="none" stroke="#f3ead8" stroke-width="2.5" stroke-dasharray="14 12"/>'
    x = lambda i: i * seg  # noqa: E731
    # 01 terraces + pin
    b += "".join(f'<path d="M{x(0) + 10} {220 + k * 9} C{x(0) + 70} {206 + k * 9} {x(0) + 130} {208 + k * 9} {x(0) + 190} {220 + k * 9}" fill="none" stroke="#b7cf9f" stroke-width="3"/>' for k in range(4))
    b += f'<g transform="translate({x(0) + 100} 196)"><path d="M0 -30 a13 13 0 0 1 13 13 c0 12 -13 25 -13 25 s-13 -13 -13 -25 a13 13 0 0 1 13 -13z" fill="{C["plan"]}"/><circle cx="0" cy="-17" r="5" fill="#fff"/></g>'
    # 02 river and canal
    b += f'<path d="M{x(1) + 150} 160 C{x(1) + 120} 210 {x(1) + 60} 230 {x(1) + 20} 268" fill="none" stroke="{C["water"]}" stroke-width="12" stroke-linecap="round"/>'
    b += f'<path d="M{x(1) + 90} 228 C{x(1) + 130} 246 {x(1) + 170} 254 {x(1) + 200} 258" fill="none" stroke="{C["water"]}" stroke-width="4" stroke-dasharray="8 5"/>'
    # 03 rain cloud and gauge
    b += cloud(x(2) + 100, 70, 1.0, "#b9c7d3", 1) + '<g stroke="#7fa7c4" stroke-width="2.5" stroke-linecap="round">' + "".join(f'<line x1="{x(2) + 76 + k * 14}" y1="94" x2="{x(2) + 70 + k * 14}" y2="112"/>' for k in range(5)) + "</g>"
    b += f'<rect x="{x(2) + 140}" y="210" width="16" height="40" rx="3" fill="#fff" stroke="{C["move"]}" stroke-width="2"/><rect x="{x(2) + 142}" y="232" width="12" height="16" fill="{C["water"]}"/>'
    # 04 patchwork fields
    for k, col in enumerate([C["teff"], C["wheat"], C["maize"], C["teff"]]):
        fx, fy = x(3) + 30 + (k % 2) * 70, 232 + (k // 2) * 26
        b += f'<path d="M{fx} {fy} h66 l6 24 h-66 z" fill="{col}" stroke="#f7f0dc" stroke-width="2"/>'
    # 05 market stall
    b += f'<g transform="translate({x(4) + 40} 222)"><rect x="0" y="0" width="120" height="44" fill="#f5e1d7"/><path d="M-6 0 h132 l-10 -20 h-112 z" fill="{C["sell"]}"/>'
    b += f'<g fill="{C["teff"]}"><circle cx="26" cy="28" r="9"/><circle cx="44" cy="30" r="8"/></g><g fill="{C["wheat"]}"><circle cx="78" cy="28" r="9"/><circle cx="96" cy="30" r="8"/></g></g>'
    # 06 cooperative store and sacks
    b += f'<g transform="translate({x(5) + 40} 200)"><path d="M0 64 V22 L60 -4 L120 22 V64 Z" fill="#e9dcc2" stroke="{C["plan"]}" stroke-width="2"/><rect x="46" y="30" width="28" height="34" fill="{C["plan"]}"/></g>'
    b += sack(x(5) + 30, 268, .8, "#e9dcc2") + sack(x(5) + 175, 268, .8, "#f1f1f1", "", "#8a8173")
    # 07 rows and ox plough
    b += "".join(f'<path d="M{x(6) + 10} {244 + k * 8} L{x(6) + 190} {240 + k * 8}" stroke="#a88b5e" stroke-width="2"/>' for k in range(4))
    b += f'<g transform="translate({x(6) + 110} 226)"><ellipse cx="0" cy="0" rx="24" ry="10" fill="#6b5428"/><circle cx="24" cy="-6" r="7" fill="#6b5428"/><path d="M-14 8 v10 M14 8 v10" stroke="#4a3a1e" stroke-width="4"/></g>'
    b += f'<path d="M{x(6) + 86} 222 L{x(6) + 50} 234" stroke="{C["wood"]}" stroke-width="3"/>' + person(x(6) + 44, 252, .8, C["produce"])
    # 08 satellite over an NDVI grid
    for k, col in enumerate(["#1a9641", "#a6d96a", "#1a9641", "#d7191c", "#1a9641", "#fdae61"]):
        b += f'<rect x="{x(7) + 30 + (k % 3) * 46}" y="{232 + (k // 3) * 22}" width="42" height="18" rx="2" fill="{col}" opacity=".85"/>'
    b += f'<path d="M{x(7) + 70} 70 L{x(7) + 30} 230 L{x(7) + 168} 230 Z" fill="#8ab8e6" opacity=".25"/>'
    b += (f'<g transform="translate({x(7) + 70} 64) rotate(-15)"><rect x="-8" y="-8" width="16" height="16" rx="3" fill="#5d6d7e"/>'
          f'<rect x="-40" y="-6" width="26" height="12" rx="2" fill="{C["move"]}"/><rect x="14" y="-6" width="26" height="12" rx="2" fill="{C["move"]}"/></g>')
    # 09 stacks and thresher
    b += "".join(f'<path d="M{x(8) + 20 + k * 34} 262 q15 -38 30 0 z" fill="{C["teff"]}" stroke="#a9843a" stroke-width="1.5"/>' for k in range(3))
    b += f'<g transform="translate({x(8) + 128} 230)"><rect x="0" y="0" width="56" height="30" rx="4" fill="{C["sell"]}"/><rect x="8" y="-14" width="24" height="16" fill="{C["sell"]}"/><circle cx="12" cy="34" r="7" fill="#263238"/><circle cx="46" cy="34" r="7" fill="#263238"/></g>'
    # 10 warehouse and silos
    b += f'<g transform="translate({x(9) + 20} 196)"><path d="M0 70 V24 L60 -2 L120 24 V70 Z" fill="#e9dcc2" stroke="{C["plan"]}" stroke-width="2"/><rect x="44" y="34" width="32" height="36" fill="{C["plan"]}"/></g>'
    b += "".join(f'<rect x="{x(9) + 148 + k * 22}" y="{186 - k * 6}" width="18" height="{80 + k * 6}" rx="9" fill="{C["stone"]}" stroke="#8a8173" stroke-width="2"/>' for k in range(2))
    # 11 truck on the road
    b += truck(x(10) + 50, 284, .9, load="#e9dcc2")
    # 12 buyer building, payments back, loop
    b += (f'<g transform="translate({x(11) + 80} 196)"><rect x="0" y="22" width="100" height="62" fill="#f5e1d7" stroke="{C["sell"]}" stroke-width="2"/>'
          f'<path d="M-6 24 L50 -6 L106 24" fill="none" stroke="{C["sell"]}" stroke-width="7" stroke-linecap="round"/><rect x="38" y="48" width="24" height="36" fill="{C["sell"]}"/></g>')
    b += tukul(x(11) + 34, 262, .8)
    b += f'<path d="M{x(11) + 78} 284 C{x(11) + 60} 296 {x(11) + 50} 294 {x(11) + 44} 286" fill="none" stroke="{C["produce"]}" stroke-width="3" stroke-dasharray="6 4" marker-end="url(#pa)"/>'
    # numbered markers and labels
    col = {"plan": C["plan"], "produce": C["produce"], "move": C["move"], "sell": C["sell"]}
    for i, s in enumerate(stages):
        cx = x(i) + seg / 2
        short = PANO_LABELS.get(s["number"], s["title"].split(" &")[0])
        b += (f'<g><circle cx="{cx}" cy="34" r="17" fill="{col[s["domain"]]}" stroke="#fff" stroke-width="3"/>'
              f'<text x="{cx}" y="39" text-anchor="middle" font-size="13" font-weight="800" fill="#fff">{s["number"]:02d}</text>'
              f'<text x="{cx}" y="354" text-anchor="middle" font-size="13" font-weight="700" fill="{C["ink"]}">{short}</text></g>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PW} {PH}" role="img" aria-labelledby="pt pd" font-family="Helvetica, Arial, sans-serif">'
            f'<title id="pt">The twelve stages as one journey</title><desc id="pd">A continuous highland panorama along one road: terraced land, a river and canal, '
            f'rain clouds, planned fields, a market, a cooperative store, ploughing, a satellite over fields, harvest, a warehouse with silos, a truck, '
            f'and a buyer paying households.</desc>{b}</svg>\n')


SCENES = {"01": s01, "02": s02, "03": s03, "04": s04, "05": s05, "06": s06, "07": s07, "08": s08, "09": s09, "10": s10, "11": s11, "12": s12}


def main(argv: list[str]) -> int:
    try:
        stages = json.loads((ROOT / "stages.json").read_text(encoding="utf-8"))["stages"]
        slug = {f"{s['number']:02d}": s["slug"] for s in stages}
        want = argv or list(SCENES)
        unknown = [w for w in want if w not in SCENES and w != "panorama"]
        if unknown:
            raise ValueError(f"Unknown stage numbers: {unknown}")
        OUT.mkdir(parents=True, exist_ok=True)
        if not argv or "panorama" in argv:
            pano = ROOT / "assets" / "img" / "chain-panorama.svg"
            pano.write_text(panorama(stages), encoding="utf-8")
            print(f"[OK] {pano.relative_to(ROOT)}")
            want = [w for w in want if w != "panorama"]
        for n in want:
            svg = SCENES[n]()
            path = OUT / f"{slug[n]}.svg"
            path.write_text(svg, encoding="utf-8")
            print(f"[OK] {path.relative_to(ROOT)} ({len(svg) / 1024:.1f} KB)")
        return 0
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

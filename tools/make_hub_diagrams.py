#!/usr/bin/env python3
"""
Draw the hub's three explanatory diagrams in the site's illustration style:

  assets/img/market-backward-pull.svg   plan backwards from the market, execute forwards from the land
  assets/img/value-chain-loop.svg       five layers from land to outcomes, enablers and the learning loop
  assets/img/platform-architecture.svg  data sources -> regional database -> stage modules -> decision support -> users

Icons are copied from assets/img/icons.svg (the <symbol>s are inlined, because an SVG shown
through <img> cannot reference an external sprite).

Usage (from the repository root, on main):
  python3 tools/make_hub_diagrams.py
  python3 tools/make_hub_diagrams.py --check     # also measure every label in Chromium (needs Playwright)
"""
from __future__ import annotations

import re
import sys
import traceback
from html import escape as E
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif'
INK, MUTED, BG, LINE = "#1f2a20", "#5d665e", "#fbfaf6", "#ddd8cb"
DOM = {  # stroke / fill / tint per domain, same as the site
    "plan": ("#74582a", "#f1e8d6"), "produce": ("#3f6b34", "#e3efdd"),
    "move": ("#2f5d8a", "#dde8f3"), "sell": ("#9a4a28", "#f5e1d7"), "grey": ("#7a857b", "#eceae4"),
}


# ------------------------------------------------------------------ helpers
def symbols(ids: list[str]) -> str:
    """Copy the named <symbol>s from the icon sprite."""
    sprite = (IMG / "icons.svg").read_text(encoding="utf-8")
    out = []
    for i in ids:
        m = re.search(rf'<symbol id="{re.escape(i)}".*?</symbol>', sprite, re.S)
        if not m:
            raise KeyError(f"icon {i} not found in icons.svg")
        out.append(m.group(0))
    return "\n".join(out)


def head(w: int, h: int, title: str, desc: str, icon_ids: list[str]) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family='{FONT}' role="img" aria-labelledby="t d">
  <title id="t">{E(title)}</title>
  <desc id="d">{E(desc)}</desc>
  <defs>
    <style>.s{{fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}} text{{fill:{INK}}} .m{{fill:{MUTED}}}</style>
    <filter id="sh" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#1f2a20" flood-opacity=".12"/></filter>
    {"".join(f'<marker id="ah-{k}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{v[0]}"/></marker>' for k, v in DOM.items())}
    {symbols(icon_ids)}
  </defs>
  <rect width="{w}" height="{h}" fill="{BG}"/>
'''


def icon(i: str, x: float, y: float, dom: str, size: int = 30) -> str:
    c, t = DOM[dom]
    r = size / 2 + 6
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" stroke="{c}" stroke-width="1.5"/>'
            f'<svg x="{x - size / 2}" y="{y - size / 2}" width="{size}" height="{size}" style="color:{c}"><use href="#{i}"/></svg>')


def lines(x: float, y: float, rows: list[str], size: float = 13, lh: float = 17, anchor: str = "start",
          cls: str = "", weight: str = "normal") -> str:
    c = f' class="{cls}"' if cls else ""
    return "".join(f'<text x="{x}" y="{y + i * lh}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"{c}>{E(r)}</text>'
                   for i, r in enumerate(rows))


def card(x, y, w, h, dom, title, rows, ic=None, chip=None) -> str:
    c, t = DOM[dom]
    s = [f'<g filter="url(#sh)"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#fff" stroke="{LINE}"/></g>',
         f'<rect x="{x}" y="{y}" width="{w}" height="6" rx="3" fill="{c}"/>']
    tx = x + 14
    if ic:
        s.append(icon(ic, x + 30, y + 34, dom, 22))
        tx = x + 58
    s.append(lines(tx, y + 32, [title], 14.5, weight="700"))
    if chip:
        s.append(f'<text x="{tx}" y="{y + 49}" font-size="11.5" font-weight="700" fill="{c}" style="fill:{c}">{E(chip)}</text>')
    s.append(lines(x + 14, y + (72 if ic else 54), rows, 12.5, 16.5, cls="m"))
    return "".join(s)


# ------------------------------------------------------------------ 1. plan backwards, execute forwards
def market_backward_pull() -> str:
    W, H = 1200, 600
    s = [head(W, H, "Plan backwards from the market, execute forwards from the land",
              "Top lane, right to left: buyer demand, logistics, crop and variety, water and climate, land suitability. "
              "They meet in the seasonal production plan. Bottom lane, left to right: inputs, planting and monitoring, "
              "forecast and harvest, storage and transport, delivery and payment. A feedback loop returns actual results to the plan.",
              ["i-01", "i-02", "i-03", "i-04", "i-05", "i-06", "i-07", "i-08", "i-09", "i-10", "i-11", "i-12"])]
    s.append(f'<text x="{W / 2}" y="40" font-size="22" font-weight="800" text-anchor="middle">Plan backwards from the market, execute forwards from the land</text>')
    # lane bands
    s.append(f'<rect x="20" y="66" width="{W - 40}" height="196" rx="18" fill="{DOM["plan"][1]}" opacity=".55"/>')
    s.append(f'<rect x="20" y="380" width="{W - 40}" height="196" rx="18" fill="{DOM["produce"][1]}" opacity=".7"/>')
    s.append(f'<text x="40" y="92" font-size="13" font-weight="800" letter-spacing="1.2" style="fill:{DOM["plan"][0]}">PLAN (pull): right to left, before the season</text>')
    s.append(f'<text x="40" y="604" font-size="13" font-weight="800" letter-spacing="1.2" style="fill:{DOM["produce"][0]}"></text>')
    s.append(f'<text x="{W - 40}" y="566" font-size="13" font-weight="800" letter-spacing="1.2" text-anchor="end" style="fill:{DOM["produce"][0]}">EXECUTE (push): left to right, during the season</text>')
    cw, gap, x0 = 200, 26, 50
    plan = [  # drawn left to right, read right to left
        ("plan", "i-01", "Land suitability", "Stage 01", ["Which plots are S1 or S2", "for that crop; slope,", "tenure, soil fixes"]),
        ("plan", "i-02", "Water and climate", "Stages 02 · 03", ["Monthly water limits;", "Meher, Belg, dry season;", "drought and frost risk"]),
        ("plan", "i-04", "Crop and variety", "Stage 04", ["Maturity that hits the", "delivery date; margin", "per hectare"]),
        ("move", "i-11", "Logistics check", "Stages 10 · 11", ["Collection centre,", "storage, truck cost", "per tonne"]),
        ("sell", "i-05", "Buyer demand", "Stage 05", ["What, how much, which", "quality, when, at what", "price"]),
    ]
    for k, (dom, ic, title, chip, rows) in enumerate(plan):
        x = x0 + k * (cw + gap)
        s.append(card(x, 104, cw, 138, dom, title, rows, ic, chip))
        if k:
            s.append(f'<path d="M{x - 3} 173 H{x - gap + 5}" stroke="{DOM["plan"][0]}" stroke-width="2.5" marker-end="url(#ah-plan)"/>')
    exe = [
        ("produce", "i-06", "Inputs on time", "Stage 06", ["Seed, fertilizer and", "credit ordered back", "from planting day"]),
        ("produce", "i-07", "Plant and irrigate", "Stage 07", ["Plots assigned, field", "calendar, on-time", "operations"]),
        ("produce", "i-08", "Monitor, forecast", "Stage 08", ["Satellite and field", "alerts; yield forecast", "for the buyer"]),
        ("move", "i-10", "Harvest and move", "Stages 09 · 10 · 11", ["Dry, grade, aggregate,", "store; shared truck", "routes"]),
        ("sell", "i-12", "Deliver and get paid", "Stage 12", ["Settle by grade, pay", "households fairly,", "measure impact"]),
    ]
    for k, (dom, ic, title, chip, rows) in enumerate(exe):
        x = x0 + k * (cw + gap)
        s.append(card(x, 404, cw, 138, dom, title, rows, ic, chip))
        if k:
            s.append(f'<path d="M{x - gap + 3} 473 H{x - 5}" stroke="{DOM["produce"][0]}" stroke-width="2.5" marker-end="url(#ah-produce)"/>')
    # the plan in the middle
    px, py, pw, ph = W / 2 - 230, 286, 460, 70
    s.append(f'<g filter="url(#sh)"><rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="35" fill="{INK}"/></g>')
    s.append(f'<text x="{W / 2}" y="{py + 30}" font-size="17" font-weight="800" text-anchor="middle" style="fill:#fff">Seasonal production plan</text>')
    s.append(f'<text x="{W / 2}" y="{py + 51}" font-size="12.5" text-anchor="middle" style="fill:#d7e3d2">best farmer income within land, monthly water and demand</text>')
    # plan lane flows into the plan (from land, the last planning step), plan flows into inputs
    s.append(f'<path d="M150 244 C150 300 260 321 {px - 4} 321" fill="none" stroke="{DOM["plan"][0]}" stroke-width="2.5" marker-end="url(#ah-plan)"/>')
    s.append(f'<path d="M{px + 40} {py + ph - 4} C{px - 20} 380 150 360 150 400" fill="none" stroke="{DOM["produce"][0]}" stroke-width="2.5" marker-end="url(#ah-produce)"/>')
    # learning loop: from payment back to the plan
    lx = x0 + 4 * (cw + gap) + cw / 2
    s.append(f'<path d="M{lx} 402 C{lx} 330 {px + pw + 120} 321 {px + pw + 6} 321" fill="none" stroke="{DOM["move"][0]}" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#ah-move)"/>')
    s.append(lines(px + pw + 50, 290, ["Actual yields, prices, losses and payment delays", "recalibrate next season's plan and the models"], 12, 15, cls="m"))
    s.append("</svg>\n")
    return "".join(s)


# ------------------------------------------------------------------ 2. layered chain with learning loop
def value_chain_loop() -> str:
    W, H = 1200, 566
    s = [head(W, H, "The chain as a self-improving network",
              "Five layers from land to outcomes, each with its contents and output, supported by cross-cutting enablers. "
              "A learning loop carries observed yields, prices and impacts back to the land suitability models.",
              ["i-01", "i-07", "i-10", "i-05", "i-12", "u-loop"])]
    s.append(f'<text x="{W / 2}" y="40" font-size="22" font-weight="800" text-anchor="middle">The chain as a self-improving network</text>')
    layers = [
        ("plan", "i-01", "1 Land", ["Soil, terrain, climate", "Water availability", "Land cover and tenure", "Suitability: FAO, AHP,", "deep learning"], "Where can what grow,", "and how well"),
        ("produce", "i-07", "2 Production", ["Crop and variety choice", "Seed and fertilizer", "Irrigation, oxen, tools", "Extension advice"], "Yield, quality,", "risk"),
        ("move", "i-10", "3 Post-harvest", ["Drying and storage", "Aggregation by co-ops", "Grading, processing", "Transport and roads"], "Losses avoided,", "value added"),
        ("sell", "i-05", "4 Market", ["Local and export buyers", "Prices and contracts", "Credit and insurance", "Digital platforms"], "Income and", "food access"),
        ("grey", "i-12", "5 Outcomes", ["Food security", "Livelihoods and jobs", "Soil and water health", "Climate resilience"], "Evidence of", "impact"),
    ]
    cw, gap, x0, y0, ch = 204, 30, 47, 70, 300
    for k, (dom, ic, title, rows, o1, o2) in enumerate(layers):
        x = x0 + k * (cw + gap)
        c, t = DOM[dom]
        s.append(f'<g filter="url(#sh)"><rect x="{x}" y="{y0}" width="{cw}" height="{ch}" rx="14" fill="#fff" stroke="{LINE}"/></g>')
        s.append(f'<path d="M{x} {y0 + 14} a14 14 0 0 1 14 -14 h{cw - 28} a14 14 0 0 1 14 14 v56 h{-cw} z" fill="{t}"/>')
        s.append(icon(ic, x + 34, y0 + 36, dom, 24))
        s.append(f'<text x="{x + 64}" y="{y0 + 42}" font-size="17" font-weight="800">{E(title)}</text>')
        s.append("".join(f'<circle cx="{x + 20}" cy="{y0 + 94 + i * 21}" r="3" fill="{c}"/>' for i in range(len(rows))))
        s.append(lines(x + 30, y0 + 98, rows, 13, 21))
        s.append(f'<rect x="{x + 12}" y="{y0 + ch - 74}" width="{cw - 24}" height="62" rx="9" fill="{t}"/>')
        s.append(f'<text x="{x + 24}" y="{y0 + ch - 55}" font-size="11" font-weight="800" letter-spacing="1" style="fill:{c}">OUTPUT</text>')
        s.append(lines(x + 24, y0 + ch - 37, [o1 + " " + o2] if len(o1 + o2) < 24 else [o1, o2], 12.5, 15, weight="600"))
        if k:
            s.append(f'<path d="M{x - gap + 4} {y0 + ch / 2} H{x - 5}" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#ah-grey)"/>')
    # enablers band
    ey = y0 + ch + 26
    s.append(f'<rect x="{x0}" y="{ey}" width="{W - 2 * x0}" height="86" rx="14" fill="#fff" stroke="{MUTED}" stroke-dasharray="5 5"/>')
    s.append(f'<text x="{W / 2}" y="{ey + 26}" font-size="14.5" font-weight="800" text-anchor="middle">Cross-cutting enablers: the network part</text>')
    s.append(lines(W / 2, ey + 48, ["Actors: farmers, cooperatives, universities, research institutes, extension, NGOs, government, private sector",
                                    "Shared infrastructure: open data platform, remote-sensing pipeline, field trial network, model registry, policy dashboard"],
                   12.5, 18, "middle", "m"))
    # learning loop from outcomes back to land, under the band
    lx1, lx2 = x0 + 4 * (cw + gap) + cw / 2, x0 + cw / 2
    ly = ey + 86
    s.append(f'<path d="M{lx1} {y0 + ch} V{ey - 8}" stroke="{DOM["sell"][0]}" stroke-width="2.5" stroke-dasharray="7 6" fill="none"/>')
    s.append(f'<path d="M{lx1} {ey + 86} C{lx1} {ly + 60} {lx2} {ly + 60} {lx2} {ey + 92}" stroke="{DOM["sell"][0]}" stroke-width="2.5" stroke-dasharray="7 6" fill="none" marker-end="url(#ah-sell)"/>')
    s.append(f'<path d="M{lx2} {ey - 4} V{y0 + ch + 6}" stroke="{DOM["sell"][0]}" stroke-width="2.5" stroke-dasharray="7 6" fill="none" marker-end="url(#ah-sell)"/>')
    s.append(f'<rect x="{W / 2 - 300}" y="{ly + 20}" width="600" height="34" rx="17" fill="{DOM["sell"][1]}"/>')
    s.append(f'<svg x="{W / 2 - 290}" y="{ly + 26}" width="22" height="22" style="color:{DOM["sell"][0]}"><use href="#u-loop"/></svg>')
    s.append(f'<text x="{W / 2 + 12}" y="{ly + 42}" font-size="13.5" font-weight="700" text-anchor="middle">Learning loop: observed yields, prices and impacts recalibrate the models</text>')
    s.append("</svg>\n")
    return "".join(s)


# ------------------------------------------------------------------ 3. platform architecture
def platform_architecture() -> str:
    W, H = 1200, 520
    s = [head(W, H, "Integrated agricultural intelligence platform",
              "Data sources feed one regional geospatial database. Analytical modules for the twelve stages read and write it, "
              "and a decision-support layer serves farmers, cooperatives, buyers, planners and transporters. A learning loop "
              "writes realised yields, prices and payments back into the database.",
              ["i-01", "i-03", "i-04", "i-05", "i-07", "i-08", "i-10", "i-11", "i-12", "d-plan", "d-produce", "d-move", "d-sell"])]
    s.append(f'<text x="{W / 2}" y="38" font-size="22" font-weight="800" text-anchor="middle">Integrated agricultural intelligence platform</text>')

    def colhead(x, label):
        return f'<text x="{x}" y="74" font-size="12" font-weight="800" letter-spacing="1.3" text-anchor="middle" class="m">{label}</text>'

    # sources
    src = [("move", "i-03", "Satellites", "Sentinel-1/2, Landsat"), ("move", "i-03", "Weather", "stations, CHIRPS, ERA5"),
           ("plan", "i-01", "Soil", "samples, iSDAsoil, SoilGrids"), ("produce", "i-07", "Field reports", "agents, mobile forms"),
           ("sell", "i-05", "Markets", "buyers and prices"), ("grey", "i-11", "Infrastructure", "roads, stores, suppliers")]
    s.append(colhead(140, "DATA SOURCES"))
    for k, (dom, ic, a, b) in enumerate(src):
        y = 90 + k * 62
        c, t = DOM[dom]
        s.append(f'<rect x="30" y="{y}" width="222" height="52" rx="10" fill="{t}" stroke="{c}" stroke-width="1.2"/>')
        s.append(f'<svg x="42" y="{y + 14}" width="24" height="24" style="color:{c}"><use href="#{ic}"/></svg>')
        s.append(f'<text x="76" y="{y + 22}" font-size="13.5" font-weight="700">{a}</text>')
        s.append(f'<text x="76" y="{y + 40}" font-size="12" class="m">{b}</text>')
        s.append(f'<path d="M254 {y + 26} C285 {y + 26} 290 {250 + (k - 2.5) * 16} 312 {250 + (k - 2.5) * 16}" fill="none" stroke="#9aa39a" stroke-width="1.6" marker-end="url(#ah-grey)"/>')
    # database
    cx, top = 400, 150
    s.append(colhead(cx, "ONE DATABASE"))
    s.append(f'<g filter="url(#sh)"><path d="M{cx - 82} {top} v200 a82 20 0 0 0 164 0 v-200" fill="#4f7f42"/></g>')
    s.append(f'<ellipse cx="{cx}" cy="{top}" rx="82" ry="20" fill="#6f9b5e"/>')
    s.append(f'<path d="M{cx - 82} {top + 68} a82 20 0 0 0 164 0 M{cx - 82} {top + 136} a82 20 0 0 0 164 0" fill="none" stroke="#6f9b5e" stroke-width="2"/>')
    s.append(lines(cx, top + 42, ["Regional", "geospatial DB"], 14.5, 18, "middle", weight="800").replace("<text ", '<text style="fill:#fff" '))
    s.append(lines(cx, top + 112, ["PostgreSQL + PostGIS"], 12, 16, "middle").replace("<text ", '<text style="fill:#e3efdd" '))
    s.append(lines(cx, top + 176, ["plots · clusters · lots", "pseudonymous IDs"], 12, 16, "middle").replace("<text ", '<text style="fill:#e3efdd" '))
    # modules
    mods = [("plan", "Suitability · water · climate", "stages 01, 02, 03"), ("plan", "Planner and market model", "stages 04, 05"),
            ("produce", "Inputs · field ops · monitoring", "stages 06, 07, 08 (PyTorch)"), ("move", "Harvest · storage · routing", "stages 09, 10, 11"),
            ("sell", "Settlement · impact · learning", "stage 12")]
    mx, mw = 530, 270
    s.append(colhead(mx + mw / 2, "STAGE MODULES"))
    for k, (dom, a, b) in enumerate(mods):
        y = 90 + k * 66
        c, t = DOM[dom]
        s.append(f'<g filter="url(#sh)"><rect x="{mx}" y="{y}" width="{mw}" height="54" rx="10" fill="#fff" stroke="{LINE}"/></g>')
        s.append(f'<rect x="{mx}" y="{y}" width="6" height="54" rx="3" fill="{c}"/>')
        s.append(f'<text x="{mx + 18}" y="{y + 23}" font-size="13.5" font-weight="700">{E(a)}</text>')
        s.append(f'<text x="{mx + 18}" y="{y + 41}" font-size="12" class="m">{E(b)}</text>')
        s.append(f'<path d="M{cx + 84} {200 + k * 28} C{cx + 105} {200 + k * 28} {mx - 30} {y + 27} {mx - 6} {y + 27}" fill="none" stroke="#9aa39a" stroke-width="1.6" marker-end="url(#ah-grey)"/>')
    # learning loop back to the database
    ly = 90 + 5 * 66 + 8
    s.append(f'<path d="M{mx + mw / 2} {ly - 10} C{mx + mw / 2} {ly + 40} {cx} {ly + 50} {cx} {top + 224}" fill="none" stroke="{DOM["sell"][0]}" stroke-width="2.2" stroke-dasharray="6 5" marker-end="url(#ah-sell)"/>')
    s.append(lines(mx + mw / 2 + 14, ly + 28, ["learning loop: realised yields, prices", "and payments update the data"], 12, 15, weight="600").replace("<text ", f'<text style="fill:{DOM["sell"][0]}" '))
    # decision support
    dx, dw = 850, 160
    s.append(colhead(dx + dw / 2, "DECISION SUPPORT"))
    s.append(f'<g filter="url(#sh)"><rect x="{dx}" y="96" width="{dw}" height="300" rx="16" fill="{INK}"/></g>')
    s.append("".join(f'<path d="M{mx + mw + 2} {117 + k * 66} L{dx - 6} {150 + k * 46}" fill="none" stroke="#9aa39a" stroke-width="1.6" marker-end="url(#ah-grey)"/>' for k in range(5)))
    for k, r in enumerate(["web maps", "dashboards", "recommendations", "SMS alerts", "buyer network", "partner API"]):
        y = 132 + k * 44
        s.append(f'<rect x="{dx + 14}" y="{y - 20}" width="{dw - 28}" height="32" rx="8" fill="#33433a"/>')
        s.append(f'<text x="{dx + dw / 2}" y="{y + 1}" font-size="13" font-weight="600" text-anchor="middle" style="fill:#fff">{r}</text>')
    # users
    users = [("produce", "d-produce", "Farmers"), ("produce", "i-10", "Cooperatives"), ("sell", "d-sell", "Buyers"),
             ("plan", "d-plan", "Planners"), ("move", "i-11", "Transporters")]
    ux = 1050
    s.append(colhead(ux + 60, "USERS"))
    for k, (dom, ic, label) in enumerate(users):
        y = 96 + k * 62
        c, t = DOM[dom]
        s.append(f'<rect x="{ux}" y="{y}" width="130" height="48" rx="24" fill="{t}" stroke="{c}" stroke-width="1.2"/>')
        s.append(f'<svg x="{ux + 12}" y="{y + 13}" width="22" height="22" style="color:{c}"><use href="#{ic}"/></svg>')
        s.append(f'<text x="{ux + 40}" y="{y + 29}" font-size="12.5" font-weight="700">{label}</text>')
        s.append(f'<path d="M{dx + dw + 2} {246} C{dx + dw + 20} 246 {ux - 22} {y + 24} {ux - 6} {y + 24}" fill="none" stroke="#9aa39a" stroke-width="1.6" marker-end="url(#ah-grey)"/>')
    s.append(f'<text x="{W / 2}" y="{H - 16}" font-size="12.5" text-anchor="middle" class="m">Personal data stays in the restricted database; the public site shows only synthetic or aggregated data.</text>')
    s.append("</svg>\n")
    return "".join(s)


# ------------------------------------------------------------------ overflow check in a real browser
CHECK_JS = """
async (svgText) => {
  document.body.innerHTML = svgText;
  const svg = document.querySelector('svg'), vb = svg.viewBox.baseVal, bad = [];
  // boxes in viewBox coordinates, so labels inside translated groups are compared correctly
  const box = (el) => { const bb = el.getBBox(), m = svg.getCTM().inverse().multiply(el.getCTM());
    const a = new DOMPoint(bb.x, bb.y).matrixTransform(m), b = new DOMPoint(bb.x + bb.width, bb.y + bb.height).matrixTransform(m);
    return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y }; };
  const rects = [...svg.querySelectorAll('rect')].filter(r => !r.closest('defs')).map(r => box(r)).filter(b => !(b.w >= vb.width - 1 && b.h >= vb.height - 1));
  for (const t of svg.querySelectorAll('text')) {
    if (!t.textContent.trim() || t.closest('defs')) continue;
    const b = box(t);
    if (b.x < -1 || b.y < -1 || b.x + b.w > vb.width + 1 || b.y + b.h > vb.height + 1) bad.push('outside canvas: ' + t.textContent);
    const cx = b.x + b.w / 2, cy = b.y + b.h / 2;
    const own = rects.filter(r => cx >= r.x && cx <= r.x + r.w && cy >= r.y && cy <= r.y + r.h).sort((p, q) => p.w * p.h - q.w * q.h)[0];
    if (own && (b.x < own.x - 1 || b.x + b.w > own.x + own.w + 1)) bad.push('overflows its box: ' + t.textContent);
  }
  return bad;
}
"""


def check(files: dict[str, str]) -> int:
    import json
    import subprocess
    js = ("const { chromium } = require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();"
          "const files=" + json.dumps(files) + ";let n=0;for(const [k,v] of Object.entries(files)){const bad=await p.evaluate(" + CHECK_JS.strip() +
          ",v);bad.forEach(x=>console.log('[FAIL] '+k+': '+x));n+=bad.length;if(!bad.length)console.log('[OK] '+k+' labels fit');}"
          "await b.close();process.exit(n?1:0);})();")
    return subprocess.run(["node", "-e", js]).returncode


# ------------------------------------------------------------------ 4. push and pull vignettes (hub "From push to pull")
def _scene(w: int, h: int, title: str, desc: str) -> list[str]:
    return [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family='{FONT}' role="img" aria-labelledby="t d">
  <title id="t">{E(title)}</title><desc id="d">{E(desc)}</desc>
  <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dcebf1"/><stop offset="1" stop-color="#f4efe2"/></linearGradient></defs>
  <rect width="{w}" height="{h}" fill="url(#sky)"/>
  <path d="M0 150 C90 120 170 132 260 112 S430 100 520 126 S{w - 40} 110 {w} 118 V{h} H0Z" fill="#c4d6b0"/>
  <path d="M0 176 C140 160 300 170 440 162 S{w - 60} 166 {w} 170 V{h} H0Z" fill="#a9c48f"/>
  <rect y="196" width="{w}" height="{h - 196}" fill="#d9c79c"/>''']


def _sack(x, y, c="#e9dcb8"):
    return (f'<path d="M{x - 13} {y} q-3 -22 6 -30 h14 q9 8 6 30 z" fill="{c}" stroke="#9c8656" stroke-width="1.5"/>'
            f'<path d="M{x - 6} {y - 30} l6 -6 l6 6" fill="none" stroke="#9c8656" stroke-width="1.5"/>')


def _person(x, y, shirt):
    return (f'<circle cx="{x}" cy="{y - 40}" r="7" fill="#6b4a32"/><path d="M{x - 7} {y - 31} h14 l3 22 h-20 z" fill="{shirt}"/>'
            f'<path d="M{x - 5} {y - 9} v9 M{x + 5} {y - 9} v9" stroke="#3a2e22" stroke-width="3" stroke-linecap="round"/>')


def vignette_push() -> str:
    W, H = 600, 240
    s = _scene(W, H, "Push: everyone sells at once", "A glut of sacks at the market at harvest, a price board with a falling red arrow, "
               "a donkey still bringing more grain and a spoiled pile on the ground.")
    # market stalls
    for i, c in enumerate(["#e9b949", "#9a4a28"]):
        x = 60 + i * 120
        s.append(f'<rect x="{x}" y="128" width="96" height="62" fill="#fff6e3" stroke="#a88d55"/><path d="M{x - 6} 128 h108 l-10 -18 h-88 z" fill="{c}"/>')
    # a glut of sacks
    for row, n in enumerate([7, 6, 5, 3]):
        for j in range(n):
            s.append(_sack(300 + j * 26 + row * 13, 214 - row * 24))
    # spoiled grain pile
    s.append('<ellipse cx="250" cy="220" rx="26" ry="7" fill="#8f8a55"/><path d="M236 214 q14 -10 28 0" fill="#a39b5f"/>')
    s.append('<g fill="#6f6a3e"><circle cx="242" cy="216" r="1.6"/><circle cx="252" cy="213" r="1.6"/><circle cx="259" cy="217" r="1.6"/></g>')
    # donkey with more sacks
    s.append('<g transform="translate(500 188)"><path d="M-30 0 h52 v-20 q0 -12 -12 -12 h-30 q-10 0 -10 12 z" fill="#8a7a6a"/>'
             '<path d="M22 -26 l16 -16 l6 4 l-10 20" fill="#8a7a6a"/><path d="M-26 0 v20 M-12 0 v20 M8 0 v20 M18 0 v20" stroke="#5d5045" stroke-width="5" stroke-linecap="round"/>'
             + _sack(-14, -30, "#e9dcb8") + _sack(10, -30, "#e9dcb8") + "</g>")
    s.append(_person(570, 210, "#3f6b34"))
    # price board falling
    s.append('<g transform="translate(70 22)"><rect width="150" height="88" rx="10" fill="#fff" stroke="#b5651d" stroke-width="2"/>'
             '<text x="14" y="24" font-size="14" font-weight="800" fill="#1f2a20">Price at harvest</text>'
             '<path d="M18 40 L52 46 L80 60 L106 70 L132 78" fill="none" stroke="#b3161a" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>'
             '<path d="M132 78 l-12 -1 l7 -9 z" fill="#b3161a"/></g>')
    s.append('<text x="440" y="40" font-size="15" font-weight="800" fill="#7a3a12">too much, too soon</text>')
    s.append("</svg>\n")
    return "".join(s)


def vignette_pull() -> str:
    W, H = 600, 240
    s = _scene(W, H, "Pull: deliver what was agreed", "A signed contract with a price band, a loaded truck on the road to the buyer's warehouse, "
               "a calendar with the delivery date and a steady price line.")
    # road
    s.append(f'<path d="M0 222 C160 206 300 214 {W} 196" stroke="#8d8d8d" stroke-width="16" fill="none"/>'
             f'<path d="M0 222 C160 206 300 214 {W} 196" stroke="#f2f2f2" stroke-width="2" stroke-dasharray="12 10" fill="none"/>')
    # buyer's warehouse
    s.append('<g transform="translate(470 104)"><rect x="0" y="30" width="110" height="64" fill="#efe3c8" stroke="#6b4f2a" stroke-width="1.5"/>'
             '<path d="M-8 34 L55 4 L118 34" fill="none" stroke="#9a4a28" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'
             '<rect x="40" y="56" width="30" height="38" fill="#6b4f2a"/><text x="55" y="48" font-size="12" font-weight="800" fill="#6b4f2a" text-anchor="middle">BUYER</text></g>')
    # truck with sacks
    s.append('<g transform="translate(250 176)"><rect x="0" y="0" width="90" height="32" rx="3" fill="#2f5d8a"/>'
             '<path d="M90 8 h24 l14 14 v10 h-38 z" fill="#3f78ad"/><rect x="98" y="11" width="13" height="9" fill="#cfe6f5"/>'
             '<circle cx="22" cy="34" r="8" fill="#263238"/><circle cx="104" cy="34" r="8" fill="#263238"/>'
             + "".join(_sack(14 + j * 20, 0) for j in range(4)) + "</g>")
    s.append('<path d="M392 196 h44" stroke="#3f6b34" stroke-width="3" stroke-dasharray="3 7" stroke-linecap="round"/><path d="M436 196 l-10 -6 v12 z" fill="#3f6b34"/>')
    # contract
    s.append('<g transform="translate(40 24) rotate(-4)"><rect width="132" height="156" rx="8" fill="#fff" stroke="#3f6b34" stroke-width="2"/>'
             '<text x="14" y="26" font-size="14" font-weight="800" fill="#1f2a20">Contract</text>'
             '<path d="M14 42 h100 M14 58 h88 M14 74 h96" stroke="#c9c2b0" stroke-width="5" stroke-linecap="round"/>'
             '<text x="14" y="102" font-size="12" font-weight="700" fill="#3f6b34">price band ±15%</text>'
             '<path d="M16 132 q14 -18 26 -2 t28 -4" fill="none" stroke="#2f5d8a" stroke-width="2.5" stroke-linecap="round"/>'
             '<circle cx="104" cy="128" r="16" fill="#3f6b34"/><path d="M96 128 l6 6 l11 -12" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></g>')
    # calendar + steady price
    s.append('<g transform="translate(212 30)"><rect width="104" height="80" rx="10" fill="#fff" stroke="#3f6b34" stroke-width="2"/>'
             '<rect width="104" height="22" rx="10" fill="#3f6b34"/><rect y="12" width="104" height="10" fill="#3f6b34"/>'
             '<text x="52" y="16" font-size="12" font-weight="800" fill="#fff" text-anchor="middle">APRIL</text>'
             + "".join(f'<rect x="{10 + (i % 6) * 15}" y="{32 + (i // 6) * 14}" width="11" height="9" rx="2" fill="{"#c43c2c" if i == 9 else "#dfe8d6"}"/>' for i in range(18))
             + '</g>')
    s.append('<g transform="translate(340 30)"><rect width="110" height="70" rx="10" fill="#fff" stroke="#3f6b34" stroke-width="2"/>'
             '<text x="12" y="20" font-size="12" font-weight="800" fill="#1f2a20">Price agreed</text>'
             '<path d="M14 50 L40 44 L64 46 L96 40" fill="none" stroke="#2f7d4a" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>'
             '<path d="M10 34 h90 M10 58 h90" stroke="#2f7d4a" stroke-width="1.2" stroke-dasharray="4 4"/></g>')
    s.append("</svg>\n")
    return "".join(s)


def main() -> int:
    files = {"market-backward-pull.svg": market_backward_pull(),
             "value-chain-loop.svg": value_chain_loop(),
             "platform-architecture.svg": platform_architecture(),
             "vignette-push.svg": vignette_push(),
             "vignette-pull.svg": vignette_pull()}
    for name, svg in files.items():
        (IMG / name).write_text(svg, encoding="utf-8")
        print(f"[OK] assets/img/{name}")
    if "--check" in sys.argv:
        return check(files)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # debugging block: say what failed and where
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

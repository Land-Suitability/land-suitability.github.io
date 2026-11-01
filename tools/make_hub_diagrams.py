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
  const svg = document.querySelector('svg');
  const rects = [...svg.querySelectorAll('rect')].filter(r => r.getAttribute('width') !== svg.viewBox.baseVal.width + '');
  const bad = [];
  const vb = svg.viewBox.baseVal;
  for (const t of svg.querySelectorAll('text')) {
    if (!t.textContent.trim()) continue;
    const b = t.getBBox();
    if (b.x < 0 || b.y < 0 || b.x + b.width > vb.width || b.y + b.height > vb.height) bad.push('outside canvas: ' + t.textContent);
    // the smallest rect that contains the text's anchor point must contain the whole text
    const ax = +t.getAttribute('x'), ay = +t.getAttribute('y');
    const owners = rects.map(r => r.getBBox()).filter(r => ax >= r.x && ax <= r.x + r.width && ay >= r.y && ay <= r.y + r.height)
      .sort((p, q) => p.width * p.height - q.width * q.height);
    if (owners.length) { const r = owners[0]; if (b.x < r.x - 1 || b.x + b.width > r.x + r.width + 1) bad.push('overflows its box: ' + t.textContent); }
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


def main() -> int:
    files = {"market-backward-pull.svg": market_backward_pull(),
             "value-chain-loop.svg": value_chain_loop(),
             "platform-architecture.svg": platform_architecture()}
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

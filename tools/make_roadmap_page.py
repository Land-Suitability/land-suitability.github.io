#!/usr/bin/env python3
"""
Build roadmap.html: Phase 1 of the build, one module at a time.

The sequence (set with the project's academic lead):
  1  Agricultural land availability and suitability   (stage 01)
  2  Water resource availability mapping              (stage 02)
  3  Irrigated land suitability analysis              (stages 01 + 02)
  4  High-value crop production guidance              (stages 04 + 07)

Each module is finished (domain model, code, tests, demo, page, validation plan) before the next
starts, and each module's output is the next module's input. Update MODULES below as work lands.

Usage (from the repository root, on main):
  python3 tools/make_roadmap_page.py
Run make_tools_page.py first: the page header is reused from tools.html.
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass, field
from html import escape as E
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = {"done": ("v0.1 built", "st-done"), "building": ("in progress", "st-build"), "next": ("next", "st-next"), "planned": ("planned", "st-plan")}


# ------------------------------------------------------------------ domain model
@dataclass(frozen=True)
class Part:
    name: str
    status: str                  # key of STATUS
    href: str = ""


@dataclass(frozen=True)
class Module:
    number: int
    title: str
    question: str
    stages: tuple[str, ...]      # stage slugs this module lives in
    icon: str
    parts: tuple[Part, ...]
    inputs: tuple[str, ...]
    output: str                  # the record handed to the next module
    done_when: tuple[str, ...]
    analogy: str = ""
    domain: str = "plan"

    @property
    def status(self) -> str:
        s = {p.status for p in self.parts}
        if s == {"done"}:
            return "done"
        if "done" in s or "building" in s:
            return "building"
        return "next" if "next" in s else "planned"


MODULES = (
    Module(1, "Agricultural land availability and suitability", "Which land may be farmed, and how well would each crop grow there?",
           ("01-land-intelligence",), "i-01",
           (Part("1a Land availability: in use, expandable, conditional, excluded", "done", "/stages/01-land-intelligence/availability/"),
            Part("1b Land suitability: FAO, AHP and deep learning, S1 to N per crop", "done", "/stages/01-land-intelligence/")),
           ("Land cover", "Elevation and slope", "Soils", "Season rainfall and temperature", "Protected areas, church forests, exclosures", "Roads and communal grazing"),
           "AvailableLand: hectares available and S1 or S2 per crop and cluster",
           ("Thresholds agreed with the woreda office and kebele land committees", "Synthetic layers replaced by the pilot woreda's real layers",
            "Cropland, forest and suitability checked against field visits"),
           "First the land's calendar (is it free?), then its skills (is it good?)."),
    Module(2, "Water resource availability mapping", "Where can water come from for that land, and how much in each month?",
           ("02-water-resources",), "i-02",
           (Part("2a Monthly water budget for a cluster (river, wells, environmental flow)", "done", "/stages/02-water-resources/"),
            Part("2b Water source maps: streams and monthly flow, springs, groundwater potential", "done", "/stages/02-water-resources/water-availability/"),
            Part("2c Water access per available field: gravity, pumped, shallow wells or harvest only", "done", "/stages/02-water-resources/water-availability/")),
           ("AvailableLand from module 1", "River network and flow records", "Rainfall and evapotranspiration", "Geology and recharge for groundwater", "Existing schemes and water-user associations"),
           "WaterAvailabilityMap: per cell, the reachable sources and the water they can give each month",
           ("Source maps checked with woreda water office records", "Monthly volumes within agreed environmental-flow limits", "Every available cell has a water-access class"),
           "A map of the wells and taps, not just the size of the tank.", "produce"),
    Module(3, "Irrigated land suitability analysis", "Which available land can be irrigated well, by which method?",
           ("01-land-intelligence", "02-water-resources"), "i-04",
           (Part("3a Irrigation land factors: slope, soil depth, texture, drainage, salinity", "next"),
            Part("3b Water access from module 2: source, distance, lift, command area", "planned"),
            Part("3c Classes S1 to N per method: surface, sprinkler, drip", "planned")),
           ("AvailableLand from module 1", "WaterAvailabilityMap from module 2", "Soil physical properties", "Irrigation method requirements"),
           "IrrigatedSuitability: S1 to N per method, and irrigable command areas with their water",
           ("Classes checked against existing irrigation schemes", "Command areas agreed with water-user associations", "Monthly water limits respected in every command area"),
           "Good land and water are not enough; they must meet: water has to reach the field at the right height and soil."),
    Module(4, "High-value crop production guidance", "Which high-value crops suit each irrigable area, and how should they be grown?",
           ("04-crop-planning", "07-farm-production"), "i-07",
           (Part("4a Crop requirements for onion, tomato, pepper, potato and garlic", "planned"),
            Part("4b Crop choice per command area: water per month, margin, market window", "planned"),
            Part("4c Production guides: calendar, inputs, irrigation schedule, post-harvest care", "planned")),
           ("IrrigatedSuitability from module 3", "Monthly water from module 2", "Prices and market windows (stage 05)", "Agronomic practice from research partners"),
           "CropGuide: recommended crops per command area, with calendar, inputs and irrigation schedule",
           ("Guides reviewed by extension and research partners", "Recommendations tested on demonstration plots", "Farmers and development agents can use them in the field"),
           "The menu is written only after we know the kitchen and the ingredients.", "sell"),
)


def build() -> str:
    tools = (ROOT / "tools.html").read_text(encoding="utf-8")
    header = tools.split("<main", 1)[0]
    rep = {"<title>Calculators | AIAE</title>": "<title>Phase 1 Roadmap | AIAE</title>",
           "tools.html\">": "roadmap.html\">",
           "social/page-tools.jpg": "social-card.png",
           "Twelve calculators, one per stage": "Phase 1: built one module at a time",
           "Move a slider, see the answer: the same formulas as each stage's Python code, on your own numbers.":
               "Land availability and suitability, water availability mapping, irrigated land suitability, high-value crop guidance."}
    for a, b in rep.items():
        if a not in header:
            raise ValueError(f"tools.html header changed, cannot find: {a[:40]}")
        header = header.replace(a, b)
    d0 = header.index('<meta name="description" content="') + len('<meta name="description" content="')
    header = header[:d0] + ("Phase 1 of the Amhara Integrated Agriculture Ecosystem, built one module at a time: agricultural land availability "
                            "and suitability, water resource availability mapping, irrigated land suitability, and high-value crop production guidance.") + header[header.index('">', d0):]
    css = '''<style>
    .flow { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin: 22px 0 8px; counter-reset: m; }
    .flow .f { position: relative; padding: 14px 16px 14px 18px; background: var(--surface); border: 1px solid var(--border); border-left: 5px solid var(--d); margin-right: 22px; border-radius: 12px; }
    .flow .f:not(:last-child)::after { content: ""; position: absolute; right: -19px; top: 50%; width: 14px; height: 14px; border-top: 3px solid var(--muted); border-right: 3px solid var(--muted); transform: translateY(-50%) rotate(45deg); }
    .flow .f b { display: block; font-size: 15px; line-height: 1.3; } .flow .f small { color: var(--muted); font-size: 12.5px; }
    .flow .f .n { font-size: 12px; font-weight: 800; color: var(--d); text-transform: uppercase; letter-spacing: .05em; }
    @media (max-width: 900px) { .flow { grid-template-columns: 1fr; gap: 18px; } .flow .f { margin-right: 0; }
      .flow .f:not(:last-child)::after { right: 50%; top: auto; bottom: -16px; transform: translateX(50%) rotate(135deg); } }
    .module { display: grid; grid-template-columns: 64px 1fr; gap: 18px; padding: 22px 0; border-top: 1px solid var(--border); }
    .module .num { width: 56px; height: 56px; border-radius: 16px; display: grid; place-items: center; background: var(--d-bg); color: var(--d); }
    .module .num svg { width: 30px; height: 30px; }
    .module h2 { margin: 0 0 4px; font-size: 24px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
    .module .q { font-size: 17px; color: var(--muted); margin: 0 0 10px; }
    .module .analogy { font-style: italic; color: var(--muted); margin: 0 0 12px; }
    .module .cols { display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 14px; }
    @media (max-width: 900px) { .module { grid-template-columns: 1fr; } .module .cols { grid-template-columns: 1fr; } }
    .module .box { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
    .module .box h3 { margin: 0 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
    .module ul { margin: 0; padding-left: 18px; } .module li { margin: 4px 0; font-size: 14.5px; }
    .parts { list-style: none; padding: 0 !important; } .parts li { display: flex; gap: 8px; align-items: baseline; }
    .out { margin-top: 10px; padding: 10px 14px; border-radius: 10px; background: var(--d-bg); font-size: 14.5px; }
    .out b { color: var(--d); }
    .badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; white-space: nowrap; }
    .st-done { background: #3f6b34; color: #fff; } .st-build { background: #1f63b8; color: #fff; } .st-next { background: #e3a64b; color: #1f2a20; } .st-plan { background: var(--surface-2); color: var(--muted); border: 1px solid var(--border); }
    .where { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .principles { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }
  </style>'''
    s0, s1 = header.index("<style>"), header.index("</style>") + len("</style>")
    header = header[:s0] + css + header[s1:]

    flow = "\n".join(f'''      <div class="f d-{m.domain}"><span class="n">Module {m.number} · <span class="badge {STATUS[m.status][1]}">{STATUS[m.status][0]}</span></span><b>{E(m.title)}</b><small>{E(m.output.split(":")[0])}</small></div>'''
                     for m in MODULES)
    blocks = []
    for m in MODULES:
        parts = "".join(f'<li><span class="badge {STATUS[p.status][1]}">{STATUS[p.status][0]}</span><span>'
                        + (f'<a href="{p.href}">{E(p.name)}</a>' if p.href else E(p.name)) + "</span></li>" for p in m.parts)
        where = "".join(f'<a class="chip" href="/stages/{s}/">Stage {s[:2]}</a>' for s in m.stages)
        blocks.append(f'''  <section class="module d-{m.domain}" id="module-{m.number}">
    <div class="num"><svg aria-hidden="true"><use href="/assets/img/icons.svg#{m.icon}"/></svg></div>
    <div>
      <h2>Module {m.number}: {E(m.title)} <span class="badge {STATUS[m.status][1]}">{STATUS[m.status][0]}</span></h2>
      <p class="q">{E(m.question)}</p>
      {f'<p class="analogy">{E(m.analogy)}</p>' if m.analogy else ""}
      <div class="cols">
        <div class="box"><h3>Parts</h3><ul class="parts">{parts}</ul></div>
        <div class="box"><h3>Inputs</h3><ul>{"".join(f"<li>{E(i)}</li>" for i in m.inputs)}</ul></div>
        <div class="box"><h3>Done when</h3><ul>{"".join(f"<li>{E(d)}</li>" for d in m.done_when)}</ul></div>
      </div>
      <div class="out"><b>Hands to the next module:</b> {E(m.output)}</div>
      <div class="where">{where}</div>
    </div>
  </section>''')
    return header + f'''<main class="container">
  <section class="hero" style="padding-bottom:4px">
    <span class="eyebrow">Build roadmap</span>
    <h1>Phase 1: built one module at a time</h1>
    <p class="lead">The twelve stages describe the whole system. Phase 1 builds its foundation in a fixed order, and each module is finished before the next one starts: first the land, then the water, then where the two meet for irrigation, and finally what to grow there.</p>
    <p class="note">Sequence set with the project's academic lead. Each module's output is the next module's input.</p>
  </section>

  <div class="flow" aria-label="Phase 1 sequence">
{flow}
  </div>

{chr(10).join(blocks)}

  <section style="padding-top:26px">
    <h2>How each module is finished</h2>
    <div class="principles">
      <div class="card"><h3>Domain model first</h3><p>The words, records and rules are agreed before code: what "available", "water access" or "irrigable" mean, and who decides the thresholds.</p></div>
      <div class="card"><h3>Code with tests</h3><p>Python (PyTorch where learning helps), with tests for every rule and clear error messages when data is missing or misaligned.</p></div>
      <div class="card"><h3>Demo, then real data</h3><p>A synthetic demo shows how the method behaves; the pilot woreda's real layers replace it, with field checks.</p></div>
      <div class="card"><h3>A page and a hand-off</h3><p>Each module gets a page with maps and a calculator, and a defined record that the next module reads.</p></div>
    </div>
  </section>

  <section style="padding-top:22px">
    <h2>Phase 1 and the twelve stages</h2>
    <p class="section-intro">Phase 1 does not replace the chain; it builds the chain's foundation first. Modules 1 and 2 deepen stages 01 and 02, module 3 joins them, and module 4 feeds the planning and field stages. Later phases complete the rest of the chain, from inputs to the market.</p>
    <p><a class="btn" href="/#chain">See all twelve stages</a> <a class="btn" href="/pilot-map.html">See them on the pilot map</a></p>
  </section>
</main>

<footer class="footer-v2">
  <div class="container"><div class="fine"><span>Status reflects the synthetic-demo versions on this site; real-data versions follow field validation.</span><span><a href="/">Back to the hub</a></span></div></div>
</footer>
</body>
</html>
'''


def main() -> int:
    nums = [m.number for m in MODULES]
    if nums != list(range(1, len(MODULES) + 1)):
        raise ValueError(f"modules must be numbered 1..n in order, got {nums}")
    for m in MODULES:
        bad = [p.status for p in m.parts if p.status not in STATUS]
        if bad:
            raise ValueError(f"module {m.number}: unknown status {bad}; use {list(STATUS)}")
    (ROOT / "roadmap.html").write_text(build(), encoding="utf-8")
    print("[OK] roadmap.html: " + ", ".join(f"{m.number} {m.status}" for m in MODULES))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # debugging block: say what failed and where
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

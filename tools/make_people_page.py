#!/usr/bin/env python3
"""
Build people.html: who does what in the chain. Ten roles drawn as simple illustrated figures
(generic, not real people) and a role x stage matrix: leads (filled) or supports (ring).

The matrix summarises what the stage pages describe; it is a design for the pilot, not a record
of agreements. Organisations are written as roles, never as named partners.

Usage (from the repository root, on main):
  python3 tools/make_people_page.py
Run make_tools_page.py first: the page header is reused from tools.html.
"""
from __future__ import annotations

import json
import sys
import traceback
from html import escape as E
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ domain model
# role id: (name, what they do, colour, hat/prop, {stage number: "L" leads | "S" supports})
ROLES = {
    "farmer": ("Farmer household", "Farms the plots, follows the field calendar, harvests, and is paid by grade.", "#3f6b34", "hat",
               {1: "S", 3: "S", 4: "S", 7: "L", 8: "S", 9: "L", 12: "L"}),
    "da": ("Development agent", "Kebele extension worker: advice, field visits, records operations and soil samples.", "#5b8c3a", "clipboard",
           {1: "S", 3: "S", 7: "L", 8: "L", 9: "S"}),
    "coop": ("Primary cooperative", "Groups members, signs contracts, orders inputs, runs collection and storage.", "#74582a", "sack",
             {4: "L", 5: "L", 6: "L", 7: "S", 9: "L", 10: "L", 11: "L", 12: "L"}),
    "union": ("Cooperative union", "Supplies inputs at scale and sells larger lots for many cooperatives.", "#8a6d3b", "box",
              {5: "S", 6: "L", 10: "S"}),
    "woreda": ("Woreda agriculture office", "Plans with the clusters, sets priorities and follows the pilot.", "#2f5d8a", "map",
               {1: "L", 2: "L", 4: "L", 6: "S", 12: "S"}),
    "wua": ("Water-user association", "Shares and manages irrigation water month by month.", "#2a78d6", "drop",
            {2: "L"}),
    "buyer": ("Buyer", "Processor, flour mill or exporter: states demand, signs the contract, grades and pays.", "#9a4a28", "scale",
              {4: "S", 5: "L", 10: "S", 12: "L"}),
    "transport": ("Transporter", "Moves inputs and grain on shared routes, before earth roads close.", "#4a5d6e", "truck",
                  {6: "S", 11: "L"}),
    "research": ("Research partner", "University or institute: calibrates models, runs trials, evaluates impact.", "#6b4f8a", "flask",
                 {1: "L", 2: "S", 3: "L", 12: "S"}),
    "platform": ("Platform team", "Runs the database, the models, the maps and the alerts behind every stage.", "#1f2a20", "laptop",
                 {1: "L", 2: "L", 3: "L", 4: "L", 5: "S", 8: "L", 11: "S"}),
}

PROPS = {  # small object each figure holds (drawn at the figure's right hand, local coords)
    "hat": '<path d="M-20 -78 h40 l-6 -10 h-28 z" fill="#e9b949"/><rect x="-11" y="-96" width="22" height="9" rx="3" fill="#e9b949"/>',
    "clipboard": '<rect x="16" y="-46" width="18" height="24" rx="2" fill="#fff" stroke="#5d665e" stroke-width="1.5"/><path d="M20 -38 h10 M20 -32 h10 M20 -26 h7" stroke="#5d665e" stroke-width="1.5"/>',
    "sack": '<path d="M14 -18 q-3 -22 6 -28 h12 q9 6 6 28 z" fill="#e9dcb8" stroke="#9c8656" stroke-width="1.5"/>',
    "box": '<rect x="14" y="-40" width="24" height="20" fill="#d9b77a" stroke="#8a6d3b" stroke-width="1.5"/><path d="M14 -34 h24" stroke="#8a6d3b" stroke-width="1.5"/>',
    "map": '<path d="M14 -44 l8 3 l8 -3 l8 3 v22 l-8 -3 l-8 3 l-8 -3 z" fill="#dde8f3" stroke="#2f5d8a" stroke-width="1.5"/><circle cx="26" cy="-34" r="2.5" fill="#c43c2c"/>',
    "drop": '<path d="M26 -48 c-8 10 -10 15 -10 19 a10 10 0 0 0 20 0 c0 -4 -2 -9 -10 -19 z" fill="#5aa0c8"/>',
    "scale": '<path d="M26 -50 v26 M14 -44 h24" stroke="#5d4a2a" stroke-width="2"/><path d="M10 -44 l-4 9 h12 z M42 -44 l-4 9 h12 z" fill="#e9b949" stroke="#8a6d3b"/>',
    "truck": '<rect x="10" y="-34" width="22" height="13" rx="2" fill="#2f5d8a"/><path d="M32 -31 h7 l5 5 v5 h-12 z" fill="#3f78ad"/><circle cx="16" cy="-19" r="3" fill="#263238"/><circle cx="37" cy="-19" r="3" fill="#263238"/>',
    "flask": '<path d="M22 -50 h8 v10 l9 18 h-26 l9 -18 z" fill="#e8e0f5" stroke="#6b4f8a" stroke-width="1.5"/><path d="M15 -26 h22 l2 4 h-26 z" fill="#9b7fc2"/>',
    "laptop": '<rect x="10" y="-42" width="28" height="18" rx="2" fill="#33433a"/><rect x="13" y="-39" width="22" height="12" fill="#8cc37a"/><path d="M6 -22 h36 l-3 4 h-30 z" fill="#5d665e"/>',
}
SKIN = ["#6b4a32", "#7a5236", "#5e3e2a", "#8a5c3c"]


def figure(i: int, colour: str, prop: str) -> str:
    """A friendly generic figure: head, body in the role colour, and the role's object."""
    skin = SKIN[i % len(SKIN)]
    return (f'<svg viewBox="-50 -110 100 120" class="fig" aria-hidden="true">'
            f'<ellipse cx="0" cy="6" rx="34" ry="6" fill="#000" opacity=".08"/>'
            f'<path d="M-22 4 v-40 q0 -18 22 -18 q22 0 22 18 v40 z" fill="{colour}"/>'
            f'<circle cx="0" cy="-70" r="15" fill="{skin}"/>'
            f'<path d="M-15 -74 q15 -16 30 0" fill="#2b211a"/>'
            f'{PROPS[prop]}</svg>')


def build(stages: list[dict]) -> str:
    cards, rows = [], []
    for i, (rid, (name, what, col, prop, m)) in enumerate(ROLES.items()):
        lead = [s for s in stages if m.get(s["number"]) == "L"]
        chips = "".join(f'<a class="chip d-{s["domain"]}" href="/stages/{s["slug"]}/">{s["number"]:02d}</a>' for s in lead)
        cards.append(f'''      <button type="button" class="person" data-role="{rid}" aria-pressed="false" style="--rc:{col}">
        {figure(i, col, prop)}
        <b>{E(name)}</b><small>{E(what)}</small>
        <span class="leads">Leads {len(lead)} · supports {sum(1 for v in m.values() if v == "S")}</span>
      </button>''')
        cells = "".join(
            f'<td class="m-{(m.get(s["number"]) or "").lower() or "n"}" data-stage="{s["number"]}">'
            + ({"L": '<span class="dot l" title="leads"></span><span class="sr">leads</span>',
                "S": '<span class="dot s" title="supports"></span><span class="sr">supports</span>'}.get(m.get(s["number"]), ""))
            + "</td>" for s in stages)
        rows.append(f'<tr data-role="{rid}"><th scope="row"><span class="sw" style="background:{col}"></span>{E(name)}</th>{cells}</tr>')
    head = "".join(f'<th scope="col" class="d-{s["domain"]}"><a href="/stages/{s["slug"]}/" title="{E(s["title"])}">'
                   f'<svg class="icon" aria-hidden="true"><use href="/assets/img/icons.svg#i-{s["number"]:02d}"/></svg>{s["number"]:02d}</a></th>' for s in stages)
    return "\n".join(cards), f'<thead><tr><th scope="col">Role</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody>'


def page(cards: str, table: str) -> str:
    tools = (ROOT / "tools.html").read_text(encoding="utf-8")
    header = tools.split("<main", 1)[0]
    rep = {"<title>Calculators | AIAE</title>": "<title>People in the Chain | AIAE</title>",
           "tools.html\">": "people.html\">",
           "social/page-tools.jpg": "social-card.png",
           "Twelve calculators, one per stage": "People in the chain",
           "Move a slider, see the answer: the same formulas as each stage's Python code, on your own numbers.":
               "Ten roles, twelve stages: who leads and who supports each step, from the farmer to the buyer."}
    for a, b in rep.items():
        if a not in header:
            raise ValueError(f"tools.html header changed, cannot find: {a[:40]}")
        header = header.replace(a, b)
    header = header.replace("assets/img/social-card.png", "assets/img/social-card.png")
    d0 = header.index('<meta name="description" content="') + len('<meta name="description" content="')
    header = header[:d0] + ("Who does what in the Amhara Integrated Agriculture Ecosystem: ten roles from farmer households and development "
                            "agents to cooperatives, buyers and transporters, and which of the twelve stages each one leads or supports.") + header[header.index('">', d0):]
    css = '''<style>
    .people { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-top: 18px; }
    @media (max-width: 1000px) { .people { grid-template-columns: repeat(3, 1fr); } }
    @media (max-width: 600px) { .people { grid-template-columns: repeat(2, 1fr); } }
    .person { font: inherit; text-align: left; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-top: 4px solid var(--rc);
      border-radius: 14px; padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 3px; cursor: pointer; transition: transform .15s ease, box-shadow .15s ease; }
    .person:hover { transform: translateY(-2px); box-shadow: 0 8px 22px rgba(0,0,0,.08); }
    .person[aria-pressed="true"] { outline: 3px solid var(--rc); outline-offset: 2px; }
    .person .fig { width: 100%; height: 104px; background: linear-gradient(#e7f0e2, #f4efe2); border-radius: 10px; margin-bottom: 6px; }
    .person b { font-size: 15px; } .person small { color: var(--muted); font-size: 12.5px; line-height: 1.4; }
    .person .leads { margin-top: auto; padding-top: 6px; font-size: 12px; font-weight: 700; color: var(--muted); }
    .matrix-wrap { margin-top: 26px; }
    table.matrix { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 14px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
    .matrix th, .matrix td { padding: 7px 6px; text-align: center; border-bottom: 1px solid var(--border); }
    .matrix tbody tr:last-child > * { border-bottom: none; }
    .matrix th[scope=row] { text-align: left; white-space: nowrap; font-weight: 600; padding-left: 12px; }
    .matrix thead th a { display: inline-flex; flex-direction: column; align-items: center; gap: 2px; color: var(--d); text-decoration: none; font-weight: 800; font-size: 12px; }
    .matrix thead th .icon { width: 20px; height: 20px; }
    .matrix .sw { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
    .matrix .dot { display: inline-block; width: 14px; height: 14px; border-radius: 50%; }
    .matrix .dot.l { background: var(--accent); } .matrix .dot.s { border: 2.5px solid var(--accent); box-sizing: border-box; }
    .matrix .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    .matrix td { position: relative; }
    .matrix.focus tbody tr:not(.on) { opacity: .3; }
    .matrix.focus tbody tr.on { background: color-mix(in srgb, var(--accent) 8%, transparent); }
    .matrix tbody tr { transition: opacity .2s ease; }
    .mkey { display: flex; gap: 16px; color: var(--muted); font-size: 13px; margin: 8px 2px 0; align-items: center; flex-wrap: wrap; }
    .mkey .dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; vertical-align: -1px; margin-right: 6px; }
    :root[data-theme="dark"] .person .fig { filter: brightness(.9); }
    @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .person .fig { filter: brightness(.9); } }
  </style>'''
    s0, s1 = header.index("<style>"), header.index("</style>") + len("</style>")
    header = header[:s0] + css + header[s1:]
    return header + f'''<main class="container">
  <section class="hero" style="padding-bottom:4px">
    <span class="eyebrow">Who does what</span>
    <h1>People in the chain</h1>
    <p class="lead">Twelve stages only work if the right people own each step. Ten roles carry the season, from farmer households and development agents to cooperatives, buyers and transporters. Select a role to see the stages it leads and supports.</p>
    <p class="note">Roles in the proposed pilot design, drawn as generic figures. Organisations that may fill them are potential partners; no agreement is implied.</p>
  </section>

  <section aria-label="Roles" style="padding-top:6px">
    <div class="people">
{cards}
    </div>
  </section>

  <section class="matrix-wrap" style="padding-top:10px">
    <h2>Who leads and who supports each stage</h2>
    <div class="table-wrap"><table class="matrix" id="matrix">{table}</table></div>
    <p class="mkey"><span><span class="dot" style="background:var(--accent)"></span>leads the stage</span><span><span class="dot" style="border:2.5px solid var(--accent)"></span>supports it</span><span>Select a role above, or a role name in the table, to focus it.</span></p>
  </section>
</main>

<footer class="footer-v2">
  <div class="container"><div class="fine"><span>Roles are part of the proposed design. Potential partners only; no agreement is implied. No personal data.</span><span><a href="/pilot-map.html">Pilot map</a> · <a href="/">Back to the hub</a></span></div></div>
</footer>
<script>
(function () {{
  "use strict";
  try {{
    var table = document.getElementById("matrix"), buttons = document.querySelectorAll(".person"), current = null;
    function focus(role) {{
      current = current === role ? null : role;
      table.classList.toggle("focus", !!current);
      table.querySelectorAll("tbody tr").forEach(function (tr) {{ tr.classList.toggle("on", tr.dataset.role === current); }});
      buttons.forEach(function (b) {{ b.setAttribute("aria-pressed", String(b.dataset.role === current)); }});
    }}
    buttons.forEach(function (b) {{ b.addEventListener("click", function () {{ focus(b.dataset.role); if (current) table.scrollIntoView({{ behavior: "smooth", block: "nearest" }}); }}); }});
    table.querySelectorAll("tbody th").forEach(function (th) {{
      th.tabIndex = 0; th.style.cursor = "pointer";
      var go = function () {{ focus(th.parentElement.dataset.role); }};
      th.addEventListener("click", go); th.addEventListener("keydown", function (e) {{ if (e.key === "Enter" || e.key === " ") {{ e.preventDefault(); go(); }} }});
    }});
  }} catch (e) {{ if (window.console) console.error("[people] interaction failed", e); }}
}})();
</script>
</body>
</html>
'''


def main() -> int:
    stages = json.loads((ROOT / "stages.json").read_text(encoding="utf-8"))["stages"]
    for rid, r in ROLES.items():
        bad = [n for n in r[4] if not 1 <= n <= len(stages)]
        if bad:
            raise ValueError(f"role {rid}: unknown stage numbers {bad}")
        if r[3] not in PROPS:
            raise KeyError(f"role {rid}: no drawing for prop {r[3]!r}")
    uncovered = [s["number"] for s in stages if not any(r[4].get(s["number"]) == "L" for r in ROLES.values())]
    if uncovered:
        raise ValueError(f"stages without a lead role: {uncovered}")
    cards, table = build(stages)
    (ROOT / "people.html").write_text(page(cards, table), encoding="utf-8")
    # all ten figures in one row, for the hub card
    row = "".join(f'<g transform="translate({60 + i * 108} 150)">' + figure(i, r[2], r[3]).replace('<svg viewBox="-50 -110 100 120" class="fig" aria-hidden="true">', "").replace("</svg>", "") + "</g>"
                  for i, r in enumerate(ROLES.values()))
    (ROOT / "assets" / "img" / "people-row.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 190" role="img" aria-label="Ten roles in the chain, drawn as generic figures">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dcebf1"/><stop offset="1" stop-color="#f4efe2"/></linearGradient></defs>'
        '<rect width="1100" height="190" fill="url(#g)"/><path d="M0 140 C200 120 400 132 600 124 S900 128 1100 122 V190 H0Z" fill="#c4d6b0"/>'
        f'{row}</svg>\n', encoding="utf-8")
    print(f"[OK] people.html ({len(ROLES)} roles x {len(stages)} stages)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # debugging block: say what failed and where
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

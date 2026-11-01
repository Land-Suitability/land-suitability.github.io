"""Generate findings.html: one illustrated finding per stage demo (synthetic data), static SVG charts."""
# Usage (from the repository root, on main): python3 tools/make_findings_page.py
# Numbers are copied from the stage pages' demo sections; update them here when a demo changes.
# Run make_tools_page.py first: the page header is reused from tools.html.
import json, html, sys, traceback


def _debug_hook(exc_type, exc, tb):
    """Error-debugging block: say what failed and where, then exit non-zero."""
    print(f"[ERROR] {exc_type.__name__}: {exc}", file=sys.stderr)
    traceback.print_exception(exc_type, exc, tb)
    sys.exit(1)


sys.excepthook = _debug_hook
from pathlib import Path
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
S = {s["slug"]: s for s in json.loads((ROOT / "stages.json").read_text())["stages"]}
E = html.escape

def fnum(v, dp=0):
    return f"{v:,.{dp}f}"

def hbars(rows, unit="", dp=0, vmax=None, hi=None):
    """Horizontal bars: rows = [(label, value)]. hi = index set drawn in full colour, others muted."""
    vmax = vmax or max(v for _, v in rows) or 1
    rh, top, lw = 30, 6, 118
    longest = max(len(f"{fnum(v, dp)}{unit}") for _, v in rows)
    bw = 192 - longest * 7.2          # leave room for the value label inside the 320 px box
    h = top + rh * len(rows)
    out = [f'<svg viewBox="0 0 320 {h}" class="fchart" role="img" aria-label="{E("; ".join(f"{l}: {fnum(v, dp)}{unit}" for l, v in rows))}">']
    for i, (l, v) in enumerate(rows):
        y = top + i * rh
        w = max(3, v / vmax * bw)
        cls = "bar" if hi is None or i in hi else "bar mute"
        out.append(f'<text class="lab" x="{lw - 8}" y="{y + 15}" text-anchor="end">{E(l)}</text>')
        out.append(f'<rect class="{cls}" x="{lw}" y="{y + 4}" width="{w:.1f}" height="16" rx="4"><title>{E(l)}: {fnum(v, dp)}{E(unit)}</title></rect>')
        out.append(f'<text class="val" x="{lw + w + 6:.1f}" y="{y + 16}">{fnum(v, dp)}{E(unit)}</text>')
    out.append("</svg>")
    return "".join(out)

def columns(cats, a, b, na, nb, unit):
    """Paired columns: a = light (capacity), b = solid (use)."""
    vmax = max(a + b); W, H, base, left = 320, 150, 122, 8
    cw = (W - left * 2) / len(cats)
    out = [f'<svg viewBox="0 0 {W} {H}" class="fchart" role="img" aria-label="{E(na)} and {E(nb)} by month">']
    out.append(f'<line class="axis" x1="{left}" x2="{W - left}" y1="{base}" y2="{base}"/>')
    for i, c in enumerate(cats):
        x = left + i * cw + 6
        ha, hb = a[i] / vmax * 104, b[i] / vmax * 104
        full = b[i] >= a[i] - 0.5
        out.append(f'<rect class="bar soft" x="{x:.1f}" y="{base - ha:.1f}" width="{cw / 2 - 4:.1f}" height="{ha:.1f}" rx="3"><title>{c} {E(na)}: {fnum(a[i])}{unit}</title></rect>')
        out.append(f'<rect class="bar" x="{x + cw / 2 - 2:.1f}" y="{base - hb:.1f}" width="{cw / 2 - 4:.1f}" height="{max(hb, 2):.1f}" rx="3"><title>{c} {E(nb)}: {fnum(b[i])}{unit}</title></rect>')
        out.append(f'<text class="lab{" strong" if full else ""}" x="{x + cw / 2 - 4:.1f}" y="{base + 16}" text-anchor="middle">{c}</text>')
        if full:
            out.append(f'<text class="val" x="{x + cw / 2 - 4:.1f}" y="{base - ha - 6:.1f}" text-anchor="middle">full</text>')
    out.append("</svg>")
    return "".join(out)

def lines(cats, series, unit):
    """series = [(name, values, cls)]; one y axis; direct labels at line ends."""
    allv = [v for _, vs, _ in series for v in vs]; lo, hi = min(allv) * .98, max(allv) * 1.01
    W, H, l, r, t, b = 320, 160, 8, 92, 10, 132
    X = lambda i: l + i * (W - l - r) / (len(cats) - 1)
    Y = lambda v: b - (v - lo) / (hi - lo) * (b - t)
    out = [f'<svg viewBox="0 0 {W} {H}" class="fchart" role="img" aria-label="{E(", ".join(n for n, _, _ in series))} by month sold">']
    out.append(f'<line class="axis" x1="{l}" x2="{W - r}" y1="{b}" y2="{b}"/>')
    for i, c in enumerate(cats):
        if i % 2 == 0:
            out.append(f'<text class="lab" x="{X(i):.1f}" y="{b + 16}" text-anchor="middle">{c}</text>')
    ends = []
    for name, vs, cls in series:
        d = "".join(f'{"M" if i == 0 else "L"}{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(vs))
        out.append(f'<path class="ln {cls}" d="{d}"/>')
        for i, v in enumerate(vs):
            out.append(f'<circle class="pt {cls}" cx="{X(i):.1f}" cy="{Y(v):.1f}" r="7"><title>{E(name)}, sold in {cats[i]}: {fnum(v)}{unit}</title></circle>')
        ends.append([Y(vs[-1]), name, cls])
    ends.sort()
    for k in range(1, len(ends)):                       # keep end labels apart
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 13)
    for y, name, cls in ends:
        out.append(f'<text class="lab end" x="{W - r + 8}" y="{y + 4:.1f}">{E(name)}</text>')
    out.append("</svg>")
    return "".join(out)

def dots(n_hit, n, label):
    out = [f'<svg viewBox="0 0 320 90" class="fchart" role="img" aria-label="{n_hit} of {n} {E(label)}">']
    for i in range(n):
        cx = 40 + i * 48
        cls = "bar" if i < n_hit else "bar mute"
        out.append(f'<circle class="{cls}" cx="{cx}" cy="38" r="17"><title>Plot {i + 1}: warned by day 70</title></circle>')
        out.append(f'<path d="M{cx - 7} 38 l5 5 l9 -10" fill="none" stroke="var(--surface)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    out.append(f'<text class="lab" x="160" y="80" text-anchor="middle">{E(label)}</text></svg>')
    return "".join(out)

def stat(big, unit, sub):
    return f'<div class="fstat"><b>{E(big)}</b><span>{E(unit)}</span><small>{E(sub)}</small></div>'

F = [
 ("01-land-intelligence", "Two sound methods disagree eightfold on the best land",
  hbars([("FAO limiting", 7.0), ("AHP weighted", 54.8)], "%", 1),
  "Share of the synthetic landscape rated S1 for teff. Both agree on what is not suitable; field trials must settle the rest."),
 ("02-water-resources", "February and March set the limit, not the season total",
  columns(["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May"], [490, 404, 334, 264, 222, 201, 250], [14.2, 63.7, 214.6, 264, 222, 151.6, 70.1],
          "Sustainable supply", "Irrigation demand", " thousand m³") + '<p class="fleg"><span><i class="sw soft"></i> Sustainable supply</span><span><i class="sw"></i> Irrigation demand</span><span>thousand m³ per month</span></p>',
  "The best wheat and onion mix fills February and March exactly; a seasonal water budget would have looked twice as roomy."),
 ("03-climate-intelligence", "A 150-day maize fits only two years in three",
  hbars([("Early teff", 100), ("Late teff", 96.7), ("Bread wheat", 90), ("Maize (mid)", 66.7)], "%", 0, 100, {3}),
  "Share of 30 synthetic years in which the season is at least as long as the crop cycle."),
 ("04-crop-planning", "One more cubic metre of March water is worth about 50 birr",
  stat("≈ 50", "birr per m³", "shadow price of March water in the cluster plan"),
  "The planner also flags contracts that cannot be met before anyone plants."),
 ("05-market-intelligence", "A price band keeps both sides in the contract",
  hbars([("Fixed price", 76.9), ("Fixed + advance", 86.5), ("Band ±15%", 98.0)], "%", 1, 100, {2}),
  "Share of 20,000 simulated delivery months in which neither side walks away."),
 ("06-input-coordination", "Order 53 days ahead to be on time 9 times in 10",
  stat("53", "days before planting", "order date from the union for a 90% on-time chance"),
  "Shortfalls are flagged in March, while there is still time to find another supplier."),
 ("07-farm-production", "Top dressing is the operation that slips",
  hbars([("Land prep", 91.9), ("Planting", 80.7), ("Basal fert.", 71.3), ("Weeding", 84.5), ("Top dressing", 57.4)], "%", 0, 100, {4}),
  "Operations done on time in the synthetic cluster. Late urea (stage 06) is the main reason."),
 ("08-monitoring-risk", "Every pest-hit plot was warned by day 70",
  dots(6, 6, "pest-hit plots warned by day 70"),
  "And the season forecast landed within 1 t of the simulated truth."),
 ("09-harvest-postharvest", "Harvest order alone removes all late plots",
  hbars([("First come", 19), ("Deadline first", 0)], " plots", 0, 19, {0}),
  "Plots harvested after their ripeness window, same crews and capacity. Tarpaulins add about 6% value."),
 ("10-storage-aggregation", "Hermetic bags turn storage into a gain",
  lines(["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"],
        [("Hermetic bags", [95000, 88988, 92020, 95002, 95977, 94991, 101725, 99747, 98746], "s1"),
         ("Sell at harvest", [95000] * 9, "ref"),
         ("Traditional", [95000, 87205, 88355, 89361, 88435, 85737, 89900, 86337, 83700], "s2")], " birr/t"),
  "Net value of a tonne of teff by month sold: +7% by May in hermetic bags; traditional bags never beat selling at harvest."),
 ("11-logistics-transport", "Shared routes cut collection cost by 14%",
  hbars([("Truck per load", 93675), ("Shared routes", 80142)], " birr", 0, None, {1}),
  "Dry-season cost to collect 176 t: 23 trips become 19. Rainy-season detours add up to 96% on some kebeles."),
 ("12-market-distribution", "The honest income gain is smaller than the naive one",
  hbars([("Before vs after", 14722), ("vs comparison", 8795)], " birr", 0, None, {1}),
  "Income gain per household. Comparing with non-pilot kebeles removes the good-year effect."),
]
tiles = []
for slug, head, chart, cap in F:
    s = S[slug]; n = f'{s["number"]:02d}'
    tiles.append(f'''    <article class="finding d-{s["domain"]} reveal">
      <a class="f-meta" href="/stages/{slug}/#demo"><svg class="icon" aria-hidden="true"><use href="/assets/img/icons.svg#i-{n}"/></svg>Stage {n} · {E(s["title"].split(" & ")[0])}</a>
      <h3>{E(head)}</h3>
      {chart}
      <p>{E(cap)}</p>
    </article>''')
page = (ROOT / "tools.html").read_text()  # reuse header from the calculators page
header = page.split("<main", 1)[0]
header = header.replace("<title>Calculators | AIAE</title>", "<title>Findings | AIAE</title>")
header = header.replace('content="Twelve small calculators, one per stage of the Amhara Integrated Agriculture Ecosystem: suitability, water need, season fit, crop mix, contracts, ordering, field calendar, NDVI, harvest loss, storage, transport and settlement."',
                        'content="Twelve findings from the stage demos of the Amhara Integrated Agriculture Ecosystem, each as a small chart: what the methods show on synthetic data."')
header = header.replace("tools.html\">", "findings.html\">").replace("social/page-tools.jpg", "social/page-findings.jpg").replace("Twelve calculators, one per stage", "Twelve findings, one per stage")
header = header.replace("Move a slider, see the answer: the same formulas as each stage's Python code, on your own numbers.", "What each stage's demo shows, in one chart each. Synthetic data, real methods.")
css_start = header.index("<style>"); css_end = header.index("</style>") + len("</style>")
header = header[:css_start] + '''<style>
    .find-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; margin-top: 22px; }
    .finding { background: var(--surface); border: 1px solid var(--border); border-top: 4px solid var(--d); border-radius: 14px; padding: 14px 16px 12px;
      display: flex; flex-direction: column; gap: 8px; color: var(--d); }
    .finding h3 { margin: 0; font-size: 18px; line-height: 1.3; color: var(--text); }
    .finding p { margin: 0; color: var(--muted); font-size: 13.5px; line-height: 1.5; }
    .f-meta { display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--d); text-decoration: none; }
    .f-meta:hover { text-decoration: underline; }
    .f-meta .icon { width: 26px; height: 26px; padding: 4px; border-radius: 8px; background: var(--d-bg); }
    .fchart { width: 100%; height: auto; overflow: visible; }
    .fchart .bar { fill: currentColor; } .fchart .bar.mute { fill: var(--muted); opacity: .35; } .fchart .bar.soft { fill: currentColor; opacity: .22; }
    .fchart .bar:hover { opacity: .8; } .fchart .bar.mute:hover { opacity: .55; }
    .fchart .lab { fill: var(--muted); font-size: 12px; } .fchart .lab.strong { fill: var(--text); font-weight: 700; }
    .fchart .val { fill: var(--text); font-size: 12.5px; font-weight: 700; }
    .fchart .axis { stroke: var(--border); stroke-width: 1; }
    .fchart .ln { fill: none; stroke-width: 2; } .fchart .ln.s1 { stroke: currentColor; } .fchart .ln.s2 { stroke: #c4521f; } .fchart .ln.ref { stroke: var(--muted); stroke-dasharray: 4 4; }
    .fchart .pt { fill: transparent; } .fchart .pt.s1:hover { fill: currentColor; } .fchart .pt.s2:hover { fill: #c4521f; } .fchart .pt.ref:hover { fill: var(--muted); }
    .fchart .lab.end { fill: var(--text); font-weight: 600; }
    .fleg { font-size: 12.5px !important; display: flex; align-items: center; gap: 4px 14px; flex-wrap: wrap; } .fleg span { white-space: nowrap; display: inline-flex; align-items: center; gap: 5px; }
    .fleg .sw { width: 12px; height: 12px; border-radius: 3px; background: var(--d); display: inline-block; } .fleg .sw.soft { opacity: .3; }
    .fstat { display: flex; flex-direction: column; align-items: flex-start; padding: 8px 0 4px; }
    .fstat b { font-size: 54px; line-height: 1; font-weight: 900; color: var(--d); }
    .fstat span { font-weight: 700; color: var(--text); margin-top: 4px; } .fstat small { color: var(--muted); font-size: 13px; }
    .find-note { margin-top: 26px; }
    :root[data-theme="dark"] .fchart .ln.s2, :root[data-theme="dark"] .fchart .pt.s2:hover { stroke: #e0703c; }
    @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .fchart .ln.s2 { stroke: #e0703c; } }
  </style>''' + header[css_end:]
body = f'''<main class="container">
  <section class="hero" style="padding-bottom:6px">
    <span class="eyebrow">What the demos show</span>
    <h1>Twelve findings, one per stage</h1>
    <p class="lead">Each stage page runs its method on synthetic data. Here is the one result from each that changes a decision, as a small chart. Hover any bar or point for its value; follow a stage link for the full demo and the code.</p>
  </section>
  <div class="page-banner" role="img" aria-label="Illustrated strip of the highland chain" style="background-position: 62% 66%"></div>
  <section class="find-grid" aria-label="Findings">
{chr(10).join(tiles)}
  </section>
  <div class="callout find-note"><strong>Synthetic data.</strong> Every number here comes from generated landscapes, weather, prices and households. They show how the methods behave and which decisions they inform; real values come from the pilot.</div>
</main>

<footer class="footer-v2">
  <div class="container"><div class="fine"><span>All results from synthetic demos. No personal farmer data is used anywhere on this site.</span><span><a href="/tools.html">Calculators</a> · <a href="/">Back to the hub</a></span></div></div>
</footer>
</body>
</html>
'''
(ROOT / "findings.html").write_text(header + body, encoding="utf-8")
print("[OK] findings.html")

"""Generate tools.html (calculators index) from stages.json + the tool list below."""
# Usage (from the repository root, on main): python3 tools/make_tools_page.py
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
DOM = {"plan": "Plan", "produce": "Produce", "move": "Move", "sell": "Sell &amp; Learn"}
# slug: (question, you set, you get)
T = {
 "01-land-intelligence": ("How suitable is my plot?", "altitude, rainfall, temperature, slope, soil pH, drainage, depth, organic carbon", "S1 to N class for teff, wheat and maize by two methods, with the main limit and whether it is fixable"),
 "02-water-resources": ("How much water does a hectare need?", "reference evapotranspiration, crop coefficient, monthly rain, irrigation method, area, water available", "the gross water need per hectare and for the area, and whether this month's water covers it"),
 "03-climate-intelligence": ("Does my variety fit the season?", "onset and length of the rains with their spread, crop cycle, planting delay", "the share of years the cycle fits, and the planting window"),
 "04-crop-planning": ("Which mix of two crops pays best?", "land, water in the leanest month, margins, water per hectare, buyer limit", "the best hectares of each crop and the shadow price of every limit"),
 "05-market-intelligence": ("Will this contract hold?", "forecast price and its uncertainty, fixed or banded price rule, band width, advance, side-selling gap", "how often both sides are better off honouring the contract"),
 "06-input-coordination": ("When must I order?", "planting date, days needed before planting, supplier lead time and predictability, on-time target", "the latest order date for the chosen confidence"),
 "07-farm-production": ("What is my field calendar?", "crop and planting date", "each operation with its target date and on-time window"),
 "08-monitoring-risk": ("Is my plot behind?", "days after planting and one NDVI reading", "a z-score against the healthy curve, with a watch or warning level"),
 "09-harvest-postharvest": ("What do drying and a late harvest cost?", "grain weight, moisture at threshing, target moisture, days harvested late", "the grain left after drying and the field losses from a late harvest"),
 "10-storage-aggregation": ("Store or sell?", "price, expected rise, months, storage technology, cost, cost of waiting", "the value per tonne of selling now or later"),
 "11-logistics-transport": ("What does it cost to move a tonne?", "distance, earth and gravel shares, load, cost per km, fixed cost, rainy-season detour", "the cost per tonne and per trip"),
 "12-market-distribution": ("How is a delivery settled?", "weight, moisture, foreign matter, grade, price, fee, households", "the net payment and the average per household"),
}
assert set(T) == set(S), set(S) ^ set(T)
cards = []
for slug, (q, inp, out) in T.items():
    s = S[slug]; n = f'{s["number"]:02d}'
    cards.append(f'''      <article class="tool-card d-{s["domain"]}" data-domain="{s["domain"]}">
        <a class="tool-media" href="/stages/{slug}/#try" tabindex="-1" aria-hidden="true"><img src="/assets/img/stages/{slug}.svg" alt="" loading="lazy"></a>
        <div class="tool-body">
          <span class="tool-meta"><svg class="icon" aria-hidden="true"><use href="/assets/img/icons.svg#i-{n}"/></svg>Stage {n} · {html.escape(s["title"])}</span>
          <h3><a href="/stages/{slug}/#try">{html.escape(q)}</a></h3>
          <dl><dt>You set</dt><dd>{html.escape(inp)}</dd><dt>You get</dt><dd>{html.escape(out)}</dd></dl>
          <span class="tool-go">Open the calculator <span aria-hidden="true">&rarr;</span></span>
        </div>
      </article>''')
page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Calculators | AIAE</title>
  <meta name="description" content="Twelve small calculators, one per stage of the Amhara Integrated Agriculture Ecosystem: suitability, water need, season fit, crop mix, contracts, ordering, field calendar, NDVI, harvest loss, storage, transport and settlement.">
  <link rel="canonical" href="https://land-suitability.github.io/tools.html">
  <meta property="og:title" content="Twelve calculators, one per stage">
  <meta property="og:description" content="Move a slider, see the answer: the same formulas as each stage's Python code, on your own numbers.">
  <meta property="og:image" content="https://land-suitability.github.io/assets/img/social-card.png">
  <meta name="theme-color" content="#3f6b34">
  <link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/assets/css/site.css">
  <script src="/assets/js/site.js"></script>
  <style>
    .tools-hero {{ display: grid; grid-template-columns: 1fr 1.15fr; gap: 28px; align-items: center; }}
    .tools-hero img {{ width: 100%; height: auto; border-radius: 18px; border: 1px solid var(--border); box-shadow: 0 10px 34px rgba(31,42,32,.12); }}
    @media (max-width: 860px) {{ .tools-hero {{ grid-template-columns: 1fr; }} }}
    .tool-filter {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 22px 0 16px; }}
    .tool-filter button {{ font: inherit; font-size: 14px; padding: 7px 14px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; }}
    .tool-filter button[aria-pressed="true"] {{ background: var(--accent); color: var(--accent-contrast); border-color: var(--accent); }}
    .tool-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 16px; }}
    .tool-card {{ position: relative; display: flex; flex-direction: column; background: var(--surface); border: 1px solid var(--border); border-top: 4px solid var(--d);
      border-radius: 14px; overflow: hidden; transition: transform .2s ease, box-shadow .2s ease; }}
    .tool-card:hover {{ transform: translateY(-3px); box-shadow: 0 10px 28px rgba(0,0,0,.09); }}
    .tool-card[hidden] {{ display: none; }}
    .tool-media img {{ display: block; width: 100%; aspect-ratio: 16 / 7; object-fit: cover; object-position: center 70%; background: #eaf2ea; }}
    .tool-body {{ padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 6px; flex: 1; }}
    .tool-meta {{ display: flex; align-items: center; gap: 8px; color: var(--d); font-size: 12.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }}
    .tool-meta .icon {{ width: 26px; height: 26px; padding: 4px; border-radius: 8px; background: var(--d-bg); }}
    .tool-card h3 {{ margin: 2px 0 4px; font-size: 19px; }}
    .tool-card h3 a {{ color: var(--text); text-decoration: none; }}
    .tool-card h3 a::after {{ content: ""; position: absolute; inset: 0; }}
    .tool-card h3 a:focus-visible {{ outline: none; }}
    .tool-card:has(h3 a:focus-visible) {{ outline: 3px solid var(--d); outline-offset: 2px; }}
    .tool-card dl {{ margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; font-size: 13.5px; }}
    .tool-card dt {{ font-weight: 700; color: var(--muted); }}
    .tool-card dd {{ margin: 0; }}
    .tool-go {{ margin-top: auto; padding-top: 8px; font-weight: 700; color: var(--d); font-size: 14px; }}
    :root[data-theme="dark"] .tool-media img, :root[data-theme="dark"] .tools-hero img {{ filter: brightness(.88) saturate(.95); }}
    @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) .tool-media img, :root:not([data-theme="light"]) .tools-hero img {{ filter: brightness(.88) saturate(.95); }} }}
  </style>
</head>
<body>
<header class="site-header">
  <div class="container">
    <a class="brand" href="/"><img class="brand-logo" src="/assets/img/favicon.svg" alt=""><span>Amhara Integrated Agriculture Ecosystem</span></a>
    <button class="nav-toggle" data-nav-toggle aria-expanded="false">Menu</button>
    <nav class="nav" aria-label="Main">
      <a href="/#loop">The loop</a>
      <a href="/#chain">Stages</a>
      <a href="/how-it-works.html">How it works</a>
      <a href="/data-spine.html">Data spine</a>
      <a href="/glossary.html">Glossary</a>
      <button class="theme-toggle" data-theme-toggle aria-label="Toggle colour theme">Theme</button>
    </nav>
  </div>
</header>

<main class="container">
  <section class="hero tools-hero" style="padding-bottom:6px">
    <div>
      <span class="eyebrow">Hands on</span>
      <h1>Twelve calculators, one per stage</h1>
      <p class="lead">Move a slider and see the answer. Each calculator uses the same formula as its stage's Python code, so you can try the method on your own numbers before reading how it works.</p>
      <p class="note">Indicative values and synthetic defaults. These are teaching tools, not advice for a real field.</p>
    </div>
    <img src="/assets/img/calculators.svg" alt="Sliders for land, water, climate and market inputs feed a result card with a gauge.">
  </section>

  <div class="tool-filter" role="group" aria-label="Filter calculators by domain">
    <button type="button" data-f="all" aria-pressed="true">All 12</button>
    <button type="button" data-f="plan" aria-pressed="false">Plan</button>
    <button type="button" data-f="produce" aria-pressed="false">Produce</button>
    <button type="button" data-f="move" aria-pressed="false">Move</button>
    <button type="button" data-f="sell" aria-pressed="false">Sell &amp; Learn</button>
  </div>
  <section class="tool-grid" aria-label="Calculators">
{chr(10).join(cards)}
  </section>
</main>

<footer class="footer-v2">
  <div class="container"><div class="fine"><span>All defaults are synthetic. No personal farmer data is used anywhere on this site.</span><span><a href="/">Back to the hub</a></span></div></div>
</footer>
<script>
(function () {{
  "use strict";
  try {{
    var btns = document.querySelectorAll(".tool-filter button"), cards = document.querySelectorAll(".tool-card");
    btns.forEach(function (b) {{ b.addEventListener("click", function () {{
      btns.forEach(function (x) {{ x.setAttribute("aria-pressed", String(x === b)); }});
      cards.forEach(function (c) {{ c.hidden = b.dataset.f !== "all" && c.dataset.domain !== b.dataset.f; }});
    }}); }});
  }} catch (e) {{ if (window.console) console.error("[tools] filter failed", e); }}
}})();
</script>
</body>
</html>
'''
(ROOT / "tools.html").write_text(page, encoding="utf-8")
print("[OK] tools.html")

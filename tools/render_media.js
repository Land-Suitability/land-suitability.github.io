#!/usr/bin/env node
/*
 * Re-render generated media from the hub's sources:
 *   assets/img/social/<slug>.jpg   one 1200 x 630 link-preview card per stage (from stages.json + stage art)
 *   assets/img/social-card.png     the hub's link-preview card
 *   assets/AIAE-concept-brief.pdf  the two-page brief (from brief.html)
 *
 * Usage (from the repository root, on main):
 *   node tools/render_media.js            # everything
 *   node tools/render_media.js cards      # only the stage cards
 *   node tools/render_media.js brief      # only the PDF
 *
 * Needs Playwright with Chromium (npm i playwright; npx playwright install chromium).
 * Run python3 tools/make_stage_art.py first if you changed a stage illustration.
 */
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const TYPES = { ".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json", ".css": "text/css",
  ".js": "text/javascript", ".png": "image/png", ".jpg": "image/jpeg", ".pdf": "application/pdf" };
const COL = { plan: "#74582a", produce: "#3f6b34", move: "#2f5d8a", sell: "#9a4a28" };
const DOMAIN = { plan: "Plan", produce: "Produce", move: "Move", sell: "Sell &amp; Learn" };
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");

function serve(extra) {
  // tiny static server for the repo root, plus in-memory pages for the card templates
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const url = decodeURIComponent(req.url.split("?")[0]);
      if (extra[url]) { res.writeHead(200, { "Content-Type": TYPES[".html"] }); return res.end(extra[url]); }
      const file = path.join(ROOT, url.endsWith("/") ? url + "index.html" : url);
      if (!file.startsWith(ROOT) || !fs.existsSync(file)) { res.writeHead(404); return res.end("not found"); }
      res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
      fs.createReadStream(file).pipe(res);
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

function stageCard(s) {
  const n = String(s.number).padStart(2, "0");
  return `<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;width:1200px;height:630px;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;overflow:hidden;background:#fbfaf6;display:grid;grid-template-columns:560px 640px}
.l{padding:56px 44px 40px 56px;display:flex;flex-direction:column;border-top:14px solid ${COL[s.domain]}}
.e{font-size:18px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:${COL[s.domain]}}
.n{font-size:110px;font-weight:900;line-height:.9;color:${COL[s.domain]};margin-top:18px}
h1{font-size:46px;line-height:1.08;margin:12px 0 16px;color:#1f2a20}
p{font-size:22px;line-height:1.4;color:#4d564e;margin:0}
.f{margin-top:auto;display:flex;align-items:center;gap:12px;font-size:17px;font-weight:700;color:#1f2a20}
.f img{width:40px;height:40px;border-radius:9px}
.r{background:url(/assets/img/stages/${s.slug}.svg) center/cover;border-top:14px solid ${COL[s.domain]}}
</style></head><body><div class="l"><div class="e">${DOMAIN[s.domain]} · Stage ${n} of 12</div><div class="n">${n}</div>
<h1>${esc(s.title)}</h1><p>${esc(s.summary)}</p><div class="f"><img src="/assets/img/favicon.svg" alt="">Amhara Integrated Agriculture Ecosystem</div></div>
<div class="r"></div></body></html>`;
}

const HUB_CARD = `<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;width:1200px;height:630px;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;overflow:hidden;background:#1f3a2c}
.bg{position:absolute;inset:0;background:url(/assets/img/hero-landscape.svg) center bottom/cover}
.shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(20,35,25,.88) 0%,rgba(20,35,25,.70) 48%,rgba(20,35,25,0) 78%)}
.t{position:absolute;left:64px;top:70px;color:#fff;width:640px}
.t .e{font-size:20px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#f2c14e}
.t h1{font-size:64px;line-height:1.05;margin:14px 0 18px}
.t p{font-size:25px;line-height:1.4;margin:0;opacity:.92}
.chips{position:absolute;left:64px;bottom:56px;display:flex;gap:10px}
.chips span{font-size:18px;font-weight:700;color:#fff;padding:8px 16px;border-radius:999px}
.logo{position:absolute;right:48px;top:44px;width:76px;height:76px;border-radius:18px;box-shadow:0 6px 20px rgba(0,0,0,.3)}
</style></head><body><div class="bg"></div><div class="shade"></div><img class="logo" src="/assets/img/favicon.svg" alt="">
<div class="t"><div class="e">Amhara Integrated Agriculture Ecosystem</div><h1>From land intelligence to market delivery</h1>
<p>Twelve connected stages, planned backwards from the market and executed forwards from the land.</p></div>
<div class="chips"><span style="background:#74582a">Plan</span><span style="background:#3f6b34">Produce</span><span style="background:#2f5d8a">Move</span><span style="background:#9a4a28">Sell &amp; Learn</span></div>
</body></html>`;

async function main() {
  let chromium;
  try { ({ chromium } = require("playwright")); }
  catch (e) { console.error("[ERROR] Playwright is not installed: npm i playwright && npx playwright install chromium"); process.exit(1); }
  const what = process.argv[2] || "all";
  const stages = JSON.parse(fs.readFileSync(path.join(ROOT, "stages.json"), "utf8")).stages;
  const pages = { "/_hub-card.html": HUB_CARD };
  stages.forEach((s) => { pages[`/_card-${s.slug}.html`] = stageCard(s); });
  const srv = await serve(pages);
  const base = `http://127.0.0.1:${srv.address().port}`;
  const browser = await chromium.launch();
  try {
    if (what === "all" || what === "cards") {
      fs.mkdirSync(path.join(ROOT, "assets/img/social"), { recursive: true });
      for (const s of stages) {
        const p = await browser.newPage({ viewport: { width: 1200, height: 630 } });   // fresh page: no cached template
        await p.goto(`${base}/_card-${s.slug}.html`); await p.waitForLoadState("networkidle");
        await p.screenshot({ path: path.join(ROOT, `assets/img/social/${s.slug}.jpg`), type: "jpeg", quality: 84 });
        await p.close();
        console.log(`[OK] assets/img/social/${s.slug}.jpg`);
      }
      const p = await browser.newPage({ viewport: { width: 1200, height: 630 } });
      await p.goto(`${base}/_hub-card.html`); await p.waitForLoadState("networkidle");
      await p.screenshot({ path: path.join(ROOT, "assets/img/social-card.png") }); await p.close();
      console.log("[OK] assets/img/social-card.png");
    }
    if (what === "all" || what === "brief") {
      const p = await browser.newPage();
      await p.goto(`${base}/brief.html`); await p.waitForSelector("body[data-ready]"); await p.waitForLoadState("networkidle");
      await p.emulateMedia({ media: "print" });
      const spare = await p.evaluate(() => [...document.querySelectorAll(".page")].map((pg) =>
        Math.round(pg.getBoundingClientRect().bottom - pg.querySelector(".foot").getBoundingClientRect().bottom)));
      if (spare.some((x) => x < 20)) throw new Error(`brief content overflows a page (space below footer: ${spare} px); shorten it`);
      await p.pdf({ path: path.join(ROOT, "assets/AIAE-concept-brief.pdf"), format: "A4", printBackground: true, preferCSSPageSize: true });
      await p.close();
      console.log("[OK] assets/AIAE-concept-brief.pdf");
    }
  } catch (e) {
    console.error("[ERROR]", e.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
    srv.close();
  }
}

main();

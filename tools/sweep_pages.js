#!/usr/bin/env node
/*
 * Front-end sweep of the assembled site: JavaScript errors, failed requests, horizontal overflow
 * and images that fail to load, on every hub page and every stage page, at phone and desktop widths.
 *
 * Usage (from the repository root, on main), against an assembled site directory:
 *   node tools/sweep_pages.js <site-dir>
 * where <site-dir> has the hub at its root and each stage branch's content under stages/<slug>/
 * (the same layout the Pages workflow builds). Without stage folders the hub placeholders are used.
 *
 * Needs Playwright with Chromium. Exit code 1 when any page has a problem.
 */
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");

const TYPES = { ".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json", ".css": "text/css",
  ".js": "text/javascript", ".png": "image/png", ".jpg": "image/jpeg", ".pdf": "application/pdf", ".xml": "application/xml", ".txt": "text/plain" };

function serve(root) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const url = decodeURIComponent(req.url.split("?")[0]);
      const file = path.join(root, url.endsWith("/") ? url + "index.html" : url);
      if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end("not found"); }
      res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
      fs.createReadStream(file).pipe(res);
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

async function main() {
  let chromium;
  try { ({ chromium } = require("playwright")); }
  catch (e) { console.error("[ERROR] Playwright is not installed: npm i playwright && npx playwright install chromium"); process.exit(2); }
  const root = path.resolve(process.argv[2] || ".");
  const stages = JSON.parse(fs.readFileSync(path.join(root, "stages.json"), "utf8")).stages;
  const hubPages = fs.readdirSync(root).filter((f) => f.endsWith(".html")).map((f) => (f === "index.html" ? "/" : "/" + f));
  const pages = [...hubPages, ...stages.map((s) => `/stages/${s.slug}/`)];
  const srv = await serve(root);
  const base = `http://127.0.0.1:${srv.address().port}`;
  const browser = await chromium.launch();
  let problems = 0;
  try {
    for (const [w, scheme] of [[390, "light"], [1280, "light"], [1280, "dark"]]) {
      const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, colorScheme: scheme });
      for (const p of pages) {
        const page = await ctx.newPage(); const errs = [];
        page.on("pageerror", (e) => errs.push("JS " + e.message));
        page.on("console", (m) => m.type() === "error" && errs.push("console " + m.text()));
        page.on("response", (r) => r.status() >= 400 && errs.push(r.status() + " " + r.url().replace(base, "")));
        await page.goto(base + p); await page.waitForLoadState("networkidle");
        await page.evaluate(() => document.querySelectorAll("img[loading=lazy]").forEach((i) => { i.loading = "eager"; }));
        await page.waitForTimeout(400);
        const r = await page.evaluate(() => ({
          overflow: document.documentElement.scrollWidth - innerWidth,
          broken: [...document.images].filter((i) => i.getAttribute("src") && i.complete && i.naturalWidth === 0).map((i) => i.getAttribute("src")),
        }));
        if (errs.length || r.overflow > 0 || r.broken.length) {
          problems++;
          console.log(`[FAIL] ${w}px ${scheme} ${p}`, JSON.stringify({ errors: errs.slice(0, 5), ...r }));
        }
        await page.close();
      }
      await ctx.close();
    }
    console.log(problems ? `[FAIL] ${problems} page view(s) with problems` : `[OK] ${pages.length} pages x 3 views, no problems`);
  } catch (e) {
    console.error("[ERROR]", e.message); problems = problems || 1;
  } finally {
    await browser.close(); srv.close();
  }
  process.exit(problems ? 1 : 0);
}

main();

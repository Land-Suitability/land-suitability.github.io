// Hub-only interactions: landscape hotspots and the value-chain wheel.
// Both are built from /stages.json, the single source of truth, so they never drift from the stage list.
(function () {
  "use strict";

  // Where each stage sits in the hero landscape (percent of the 1200 x 600 illustration)
  var HOTSPOTS = {
    "01": [7.5, 62], "02": [46.5, 57], "03": [59, 23], "04": [37.5, 75], "05": [89, 87],
    "06": [82.5, 75.5], "07": [67, 71], "08": [12.5, 12], "09": [55.5, 82.5], "10": [94, 69],
    "11": [82, 94], "12": [22, 59]
  };
  var DOMAIN_VAR = { plan: "--plan", produce: "--produce", move: "--move", sell: "--sell" };

  function el(tag, attrs, html) {
    var e = document.createElementNS(tag === "a" || tag === "div" || tag === "span" ? "http://www.w3.org/1999/xhtml" : "http://www.w3.org/2000/svg", tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function hotspots(stages) {
    var scene = document.getElementById("scene");
    if (!scene) return;
    stages.forEach(function (s) {
      var n = String(s.number).padStart(2, "0"), pos = HOTSPOTS[n];
      if (!pos) return;
      var a = document.createElement("a");
      // labels near an edge open inwards so they are never clipped
      a.className = "hotspot d-" + s.domain + (pos[0] > 68 ? " hs-r" : pos[0] < 32 ? " hs-l" : "");
      a.href = "/stages/" + s.slug + "/";
      a.style.left = pos[0] + "%";
      a.style.top = "calc(" + pos[1] + "% * var(--img-share, 1))";
      a.setAttribute("aria-label", "Stage " + n + ": " + s.title);
      a.innerHTML = n + '<span class="hs-label">' + n + " · " + s.title + "</span>";
      scene.appendChild(a);
    });
    // hotspots are positioned against the image only, not the caption below it
    function fit() {
      var img = scene.querySelector("img");
      if (img && scene.clientHeight) scene.style.setProperty("--img-share", img.clientHeight / scene.clientHeight);
    }
    fit();
    window.addEventListener("resize", fit);
    var img = scene.querySelector("img");
    if (img && !img.complete) img.addEventListener("load", fit);
  }

  function wheel(stages, domains) {
    var host = document.getElementById("wheel"), panel = document.getElementById("wheel-panel");
    if (!host || !panel) return;
    var W = 520, C = W / 2, R = 172, r = 30, n = stages.length;
    var svg = el("svg", { viewBox: "0 0 " + W + " " + W, role: "group", "aria-label": "Twelve stages arranged in a loop" });
    var defs = el("defs", {}, '<marker id="wh-arrow" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,1 L9,5 L0,9 z" fill="#9aa39b"/></marker>');
    svg.appendChild(defs);

    // domain arcs behind the nodes
    var byDomain = {};
    stages.forEach(function (s, i) { (byDomain[s.domain] = byDomain[s.domain] || []).push(i); });
    function pt(i, rad) { var a = -Math.PI / 2 + (2 * Math.PI * i) / n; return [C + rad * Math.cos(a), C + rad * Math.sin(a)]; }
    Object.keys(byDomain).forEach(function (d) {
      var idx = byDomain[d], a0 = idx[0] - 0.45, a1 = idx[idx.length - 1] + 0.45;
      var p0 = pt(a0, R + 42), p1 = pt(a1, R + 42), large = (a1 - a0) / n > 0.5 ? 1 : 0;
      var arc = el("path", { d: "M" + p0[0] + "," + p0[1] + " A" + (R + 42) + "," + (R + 42) + " 0 " + large + " 1 " + p1[0] + "," + p1[1],
        fill: "none", stroke: "var(" + DOMAIN_VAR[d] + ")", "stroke-width": 8, "stroke-linecap": "round", opacity: ".35" });
      svg.appendChild(arc);
      var mid = pt((a0 + a1) / 2, R + 62), dom = domains.filter(function (x) { return x.id === d; })[0];
      var t = el("text", { x: mid[0], y: mid[1] + 4, "text-anchor": "middle", "font-size": 12, "font-weight": 700, fill: "var(" + DOMAIN_VAR[d] + ")",
        "letter-spacing": ".08em" });
      t.textContent = (dom ? dom.title : d).toUpperCase();
      svg.appendChild(t);
    });

    // loop arrows between consecutive stages (12 -> 01 closes the loop)
    for (var i = 0; i < n; i++) {
      var a = pt(i + 0.28, R), b = pt(i + 0.72, R);
      svg.appendChild(el("path", { d: "M" + a[0] + "," + a[1] + " A" + R + "," + R + " 0 0 1 " + b[0] + "," + b[1], fill: "none",
        stroke: "var(--border)", "stroke-width": 3, "marker-end": "url(#wh-arrow)", style: "color:var(--muted)" }));
    }

    // centre
    svg.appendChild(el("circle", { cx: C, cy: C, r: 92, fill: "var(--surface)", stroke: "var(--border)", "stroke-width": 1.5 }));
    var cIcon = el("use", { href: "/assets/img/icons.svg#u-loop", x: C - 20, y: C - 52, width: 40, height: 40, style: "color:var(--accent)" });
    svg.appendChild(cIcon);
    var ct = el("text", { x: C, y: C + 10, "text-anchor": "middle", "font-size": 15, "font-weight": 700, fill: "var(--text)" });
    ct.textContent = "Learning loop";
    svg.appendChild(ct);
    var cs = el("text", { x: C, y: C + 30, "text-anchor": "middle", "font-size": 12, fill: "var(--muted)" });
    cs.textContent = "12 stages · 4 domains";
    svg.appendChild(cs);

    var nodes = [];
    stages.forEach(function (s, i) {
      var p = pt(i, R), n2 = String(s.number).padStart(2, "0");
      var g = el("g", { class: "node d-" + s.domain, tabindex: 0, role: "link", "aria-label": "Stage " + n2 + ": " + s.title });
      g.appendChild(el("circle", { class: "bg", cx: p[0], cy: p[1], r: r, fill: "var(--surface)", stroke: "var(" + DOMAIN_VAR[s.domain] + ")", "stroke-width": 3 }));
      g.appendChild(el("use", { href: "/assets/img/icons.svg#i-" + n2, x: p[0] - 13, y: p[1] - 17, width: 26, height: 26,
        style: "color:var(" + DOMAIN_VAR[s.domain] + ")" }));
      var num = el("text", { x: p[0], y: p[1] + 21, "text-anchor": "middle", "font-size": 10, "font-weight": 700, fill: "var(--muted)" });
      num.textContent = n2;
      g.appendChild(num);
      function show() {
        nodes.forEach(function (x) { x.classList.remove("active"); });
        g.classList.add("active");
        var dom = domains.filter(function (x) { return x.id === s.domain; })[0];
        var link = function (slug) {
          var t = stages.filter(function (x) { return x.slug === slug; })[0];
          return t ? '<a class="chip" href="/stages/' + t.slug + '/">' + String(t.number).padStart(2, "0") + " " + t.title + "</a>" : "";
        };
        panel.style.setProperty("--d", "var(" + DOMAIN_VAR[s.domain] + ")");
        panel.innerHTML =
          '<span class="pill d-' + s.domain + '"><svg class="icon" aria-hidden="true"><use href="/assets/img/icons.svg#d-' + s.domain + '"/></svg>' + (dom ? dom.title : "") + "</span>" +
          "<h3>" + n2 + ". " + s.title + "</h3><p>" + s.summary + "</p>" +
          (s.upstream.length ? '<p style="margin:12px 0 4px;font-size:13px;color:var(--muted)">Receives from</p><div class="flowlinks">' + s.upstream.map(link).join("") + "</div>" : "") +
          (s.downstream.length ? '<p style="margin:12px 0 4px;font-size:13px;color:var(--muted)">Feeds into</p><div class="flowlinks">' + s.downstream.map(link).join("") + "</div>" : "") +
          '<p style="margin-top:16px"><a class="btn primary" href="/stages/' + s.slug + '/">Open stage ' + n2 + " &rarr;</a></p>";
      }
      g.addEventListener("mouseenter", show);
      g.addEventListener("focus", show);
      // touch screens have no hover: first tap shows the details, a second tap opens the stage
      // remember the state at touch-down: the focus event that follows a tap already marks the node active
      var lastPointer = "mouse", wasActive = false;
      g.addEventListener("pointerdown", function (e) { lastPointer = e.pointerType || "mouse"; wasActive = g.classList.contains("active"); });
      g.addEventListener("click", function () {
        var touch = lastPointer === "touch" || lastPointer === "pen";
        if (touch && !wasActive) { show(); panel.scrollIntoView({ behavior: "smooth", block: "nearest" }); return; }
        location.href = "/stages/" + s.slug + "/";
      });
      g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); location.href = "/stages/" + s.slug + "/"; } });
      nodes.push(g);
      svg.appendChild(g);
    });
    host.appendChild(svg);
  }

  function init() {
    fetch("/stages.json")
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) { hotspots(d.stages); wheel(d.stages, d.domains); })
      .catch(function (e) { if (window.console) console.error("[hub] could not load stages.json", e); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();

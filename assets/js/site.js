// Shared behaviour for the hub and every stage page (stage branches link /assets/js/site.js).
// Everything here is progressive enhancement: pages work without it.
(function () {
  "use strict";
  var root = document.documentElement;
  var ICONS = "/assets/img/icons.svg";
  var DOMAIN_VAR = { plan: "--plan", produce: "--produce", move: "--move", sell: "--sell" };

  function safeGet(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function safeSet(key, val) { try { localStorage.setItem(key, val); } catch (e) { /* storage blocked */ } }
  function icon(id, cls) { return '<svg class="icon' + (cls ? " " + cls : "") + '" aria-hidden="true"><use href="' + ICONS + "#" + id + '"/></svg>'; }
  function log(msg, e) { if (window.console) console.warn("[site] " + msg, e || ""); }

  // theme must apply before first paint to avoid a flash
  var saved = safeGet("aiae-theme");
  if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);

  var stagesPromise = null;
  function stages() {
    if (!stagesPromise) {
      stagesPromise = fetch("/stages.json").then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      });
    }
    return stagesPromise;
  }
  function pad(n) { return String(n).padStart(2, "0"); }
  function currentSlug() { var m = location.pathname.match(/^\/stages\/([^/]+)\//); return m ? m[1] : null; }

  // stage branches carry an older text badge; show the shared logo everywhere
  function brandLogo() {
    var mark = document.querySelector(".brand .brand-mark");
    if (!mark) return;
    var img = document.createElement("img");
    img.className = "brand-logo"; img.src = "/assets/img/favicon.svg"; img.alt = "";
    mark.replaceWith(img);
  }

  function favicon() {
    if (document.querySelector('link[rel="icon"]')) return;
    var l = document.createElement("link");
    l.rel = "icon"; l.type = "image/svg+xml"; l.href = "/assets/img/favicon.svg";
    document.head.appendChild(l);
  }

  function themeToggle() {
    var toggle = document.querySelector("[data-theme-toggle]");
    if (!toggle) return;
    function isDark() {
      return (root.getAttribute("data-theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
    }
    function paint() {
      toggle.innerHTML = icon(isDark() ? "u-sun" : "u-moon");
      toggle.setAttribute("aria-label", isDark() ? "Switch to light theme" : "Switch to dark theme");
      toggle.title = toggle.getAttribute("aria-label");
    }
    toggle.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      safeSet("aiae-theme", next);
      paint();
    });
    paint();
  }

  function mobileNav() {
    var navBtn = document.querySelector("[data-nav-toggle]"), nav = document.querySelector(".nav");
    if (!navBtn || !nav) return;
    navBtn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      navBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // ---------------- quick-jump palette (Ctrl/Cmd + K or "/")
  function palette() {
    var nav = document.querySelector(".nav");
    var btn = document.createElement("button");
    btn.className = "tool-btn"; btn.type = "button";
    btn.innerHTML = icon("u-search") + "<span>Jump</span><kbd>Ctrl K</kbd>";
    btn.setAttribute("aria-label", "Jump to a stage (Ctrl+K)");
    var themeBtn = document.querySelector("[data-theme-toggle]");
    if (nav) nav.insertBefore(btn, themeBtn || null);

    var back = document.createElement("div");
    back.className = "palette-backdrop";
    back.innerHTML = '<div class="palette" role="dialog" aria-modal="true" aria-label="Jump to a stage">' +
      '<input type="search" placeholder="Type a stage, topic or number… (e.g. water, 08, contract)" aria-label="Search stages">' +
      '<ul role="listbox"></ul><div class="foot">↑ ↓ to move · Enter to open · Esc to close</div></div>';
    document.body.appendChild(back);
    var input = back.querySelector("input"), list = back.querySelector("ul"), items = [], sel = 0;

    var extra = [
      { title: "Home: the landscape and the loop", href: "/", sub: "Hub portal", icon: "u-loop", domain: "" },
      { title: "How it works, step by step", href: "/how-it-works.html", sub: "The story of one season", icon: "d-plan", domain: "" },
      { title: "Data spine: every hand-off", href: "/data-spine.html", sub: "Which stage sends which record to which", icon: "d-move", domain: "" },
      { title: "Glossary", href: "/glossary.html", sub: "Terms from kebele to shadow price", icon: "u-search", domain: "" }
    ];
    function render(q) {
      q = (q || "").toLowerCase().trim();
      list.innerHTML = "";
      items = [];
      stages().then(function (d) {
        var all = d.stages.map(function (s) {
          return { title: pad(s.number) + ". " + s.title, href: "/stages/" + s.slug + "/", sub: s.summary, icon: "i-" + pad(s.number),
            domain: s.domain, hay: (pad(s.number) + " " + s.title + " " + s.summary + " " + (s.questions || []).join(" ") + " " +
              (s.components || []).join(" ") + " " + s.domain).toLowerCase() };
        }).concat(extra.map(function (x) { x.hay = (x.title + " " + x.sub).toLowerCase(); return x; }));
        var words = q.split(/\s+/).filter(Boolean);
        all.filter(function (x) { return words.every(function (w) { return x.hay.indexOf(w) !== -1; }); }).forEach(function (x) {
          var li = document.createElement("li");
          var style = x.domain ? ' style="--d:var(' + DOMAIN_VAR[x.domain] + ");--d-bg:var(" + DOMAIN_VAR[x.domain] + '-bg)"' : "";
          li.innerHTML = '<a href="' + x.href + '"' + style + ">" + icon(x.icon) + "<span>" + x.title + "<small>" + x.sub + "</small></span></a>";
          list.appendChild(li);
          items.push(li.firstChild);
        });
        if (!items.length) list.innerHTML = '<li style="padding:14px;color:var(--muted)">No match. Try "water", "price" or a number.</li>';
        sel = 0; mark();
      }).catch(function (e) { list.innerHTML = '<li style="padding:14px">Could not load the stage list.</li>'; log("palette", e); });
    }
    function mark() { items.forEach(function (a, i) { a.classList.toggle("sel", i === sel); if (i === sel) a.scrollIntoView({ block: "nearest" }); }); }
    function open() { back.classList.add("open"); input.value = ""; render(""); setTimeout(function () { input.focus(); }, 10); }
    function close() { back.classList.remove("open"); btn.focus(); }
    btn.addEventListener("click", open);
    back.addEventListener("click", function (e) { if (e.target === back) close(); });
    input.addEventListener("input", function () { render(input.value); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { sel = Math.min(items.length - 1, sel + 1); mark(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { sel = Math.max(0, sel - 1); mark(); e.preventDefault(); }
      else if (e.key === "Enter" && items[sel]) { location.href = items[sel].getAttribute("href"); }
      else if (e.key === "Escape") { close(); }
    });
    document.addEventListener("keydown", function (e) {
      var typing = /input|textarea|select/i.test((e.target && e.target.tagName) || "");
      if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) { e.preventDefault(); back.classList.contains("open") ? close() : open(); }
      else if (e.key === "/" && !typing && !back.classList.contains("open")) { e.preventDefault(); open(); }
      else if (e.key === "Escape" && back.classList.contains("open")) { close(); }
    });
  }

  // ---------------- reading progress + back to top
  function progressAndTop() {
    var bar = document.createElement("div"); bar.className = "progress-bar"; bar.setAttribute("aria-hidden", "true");
    var top = document.createElement("button"); top.className = "to-top"; top.type = "button";
    top.setAttribute("aria-label", "Back to top"); top.innerHTML = icon("u-arrow-up");
    document.body.appendChild(bar); document.body.appendChild(top);
    top.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    var ticking = false;
    function update() {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = (h > 0 ? (window.scrollY / h) * 100 : 0) + "%";
      top.classList.toggle("show", window.scrollY > 600);
      ticking = false;
    }
    window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }

  // ---------------- lightbox for diagrams (click to enlarge, Esc to close)
  function lightbox() {
    var imgs = document.querySelectorAll("figure.diagram img, img.zoomable");
    if (!imgs.length) return;
    var box = document.createElement("div");
    box.className = "lightbox"; box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true"); box.setAttribute("aria-label", "Enlarged diagram");
    box.innerHTML = '<button class="lb-close" type="button" aria-label="Close">&times;</button><div><img alt=""><div class="lb-cap"></div></div>';
    document.body.appendChild(box);
    var big = box.querySelector("img"), cap = box.querySelector(".lb-cap"), last = null;
    function close() { box.classList.remove("open"); if (last) last.focus(); }
    imgs.forEach(function (im) {
      im.setAttribute("tabindex", "0");
      im.setAttribute("role", "button");
      im.setAttribute("aria-label", "Enlarge: " + (im.alt || "diagram"));
      function open() {
        last = im; big.src = im.currentSrc || im.src; big.alt = im.alt;
        var fc = im.closest("figure") && im.closest("figure").querySelector("figcaption");
        cap.textContent = fc ? fc.textContent : (im.alt || "");
        box.classList.add("open"); box.querySelector(".lb-close").focus();
      }
      im.addEventListener("click", open);
      im.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    });
    box.addEventListener("click", function (e) { if (e.target === box || e.target === big || e.target.classList.contains("lb-close")) close(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && box.classList.contains("open")) close(); });
  }

  // ---------------- animated numbers (counts up once when visible)
  function countUp() {
    var els = document.querySelectorAll("[data-count]");
    if (!els.length || !("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        var el = en.target, end = parseFloat(el.dataset.count), t0 = null, dur = 900;
        function step(t) { if (!t0) t0 = t; var k = Math.min(1, (t - t0) / dur); el.textContent = Math.round(end * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); }
        requestAnimationFrame(step);
      });
    }, { threshold: .6 });
    els.forEach(function (e) { io.observe(e); });
  }

  // ---------------- keyboard access to horizontally scrollable tables
  function scrollableTables() {
    document.querySelectorAll(".table-wrap, .spine-wrap").forEach(function (w) {
      if (w.scrollWidth > w.clientWidth + 2 && !w.hasAttribute("tabindex")) {
        w.setAttribute("tabindex", "0");
        w.setAttribute("role", "region");
        var cap = w.querySelector("caption, th");
        w.setAttribute("aria-label", "Scrollable table" + (cap ? ": " + cap.textContent.trim().slice(0, 60) : ""));
      }
    });
  }

  // ---------------- reveal on scroll
  function reveal() {
    var els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) { els.forEach(function (e) { e.classList.add("in"); }); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    els.forEach(function (e) { io.observe(e); });
  }

  // ---------------- stage pages: chain navigator, hero art, scroll spy
  function stagePage() {
    var slug = currentSlug();
    if (!slug) return;
    stages().then(function (d) {
      var me = d.stages.filter(function (s) { return s.slug === slug; })[0];
      if (!me) return;
      // chain navigator strip under the header
      var strip = document.createElement("nav");
      strip.className = "chain-nav"; strip.setAttribute("aria-label", "All twelve stages");
      strip.innerHTML = '<div class="container"><span class="cn-label">' + icon("u-loop") + "The chain</span>" + d.stages.map(function (s) {
        var cur = s.slug === slug;
        return '<a href="/stages/' + s.slug + '/" class="cn d-' + s.domain + (cur ? " cur" : "") + '"' + (cur ? ' aria-current="page"' : "") +
          ' title="' + pad(s.number) + ". " + s.title + '">' + icon("i-" + pad(s.number)) + "<span>" + pad(s.number) + "</span></a>";
      }).join("") + "</div>";
      var header = document.querySelector(".site-header");
      if (header) header.insertAdjacentElement("afterend", strip);
      var cur = strip.querySelector(".cur");
      if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest", inline: "center" });

      // stage illustration next to the hero text
      var hero = document.querySelector(".stage-hero");
      if (hero && !hero.querySelector(".stage-art")) {
        var art = new Image();
        art.className = "stage-art"; art.alt = ""; art.decoding = "async";
        art.onload = function () { hero.classList.add("has-art"); hero.insertBefore(art, hero.firstChild); };
        art.onerror = function () { /* no illustration yet for this stage */ };
        art.src = "/assets/img/stages/" + slug + ".svg";
      }
      // rich previous / next cards with illustrations (the loop wraps from 12 back to 01)
      var pager = document.querySelector(".pager");
      if (pager) {
        var i = d.stages.indexOf(me), n = d.stages.length;
        var prev = d.stages[(i - 1 + n) % n], next = d.stages[(i + 1) % n];
        var card = function (s, dir) {
          var dv = DOMAIN_VAR[s.domain];
          return '<a class="pager-card ' + dir + '" href="/stages/' + s.slug + '/" style="--d:var(' + dv + ');--d-bg:var(' + dv + '-bg)">' +
            '<img src="/assets/img/stages/' + s.slug + '.svg" alt="" loading="lazy">' +
            '<span class="pc-text"><small>' + (dir === "prev" ? "&larr; Previous stage" : (i === n - 1 ? "Next season starts again &rarr;" : "Next stage &rarr;")) +
            "</small><b>" + pad(s.number) + ". " + s.title + "</b><span>" + s.summary + "</span></span></a>";
        };
        pager.classList.add("pager-rich");
        pager.innerHTML = card(prev, "prev") + card(next, "next");
      }

      // stage icon in the hero pill
      var pill = hero && hero.querySelector(".pill");
      if (pill && !pill.querySelector("svg")) pill.insertAdjacentHTML("afterbegin", icon("d-" + me.domain));
    }).catch(function (e) { log("stage navigator", e); });

    // scroll spy on the on-page table of contents
    var chips = document.querySelectorAll(".toc a[href^='#']");
    if (!chips.length || !("IntersectionObserver" in window)) return;
    var map = {};
    chips.forEach(function (c) { var t = document.getElementById(c.getAttribute("href").slice(1)); if (t) map[t.id] = c; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting && map[en.target.id]) {
          chips.forEach(function (c) { c.classList.remove("active"); });
          map[en.target.id].classList.add("active");
        }
      });
    }, { rootMargin: "-30% 0px -60% 0px" });
    Object.keys(map).forEach(function (id) { io.observe(document.getElementById(id)); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var steps = [favicon, brandLogo, themeToggle, mobileNav, palette, progressAndTop, reveal, stagePage, scrollableTables, lightbox, countUp];
    steps.forEach(function (fn) { try { fn(); } catch (e) { log(fn.name + " failed", e); } });
  });
})();

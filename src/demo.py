#!/usr/bin/env python3
"""
Stage 08 demo on SYNTHETIC satellite series (generated NDVI, not real Sentinel-2 data).

  1. Generate 600 past plot-seasons of teff (NDVI every 5 days, ~30% cloudy, known yields) for training
  2. Current season, cluster A: 60 plots; 6 plots hit by a pest outbreak from day 45
  3. Alerts at day 70; cause hint from how widespread the problem is
  4. Cluster production forecast at days 40, 55, 70, 85, 100 (linear baseline, and PyTorch with MC dropout)
Writes assets/demo-monitoring.json for the charts.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monitoring import CropCurve, NDVISeries, clean_and_smooth, detect_alerts, features, fit_linear, forecast_linear  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CURVE = CropCurve("teff")
DAYS = np.arange(0, 141, 5)


def simulate_plot(rng, pid, vigour, stress_from=None, stress_depth=0.0):
    """NDVI = curve x vigour, minus a stress dip if any; yield follows the season's green biomass."""
    ndvi = CURVE.base + (CURVE.expected(DAYS) - CURVE.base) * vigour
    if stress_from is not None:
        ndvi = ndvi - stress_depth * np.clip((DAYS - stress_from) / 15, 0, 1) * (DAYS < 120)
    ndvi = ndvi + rng.normal(0, 0.02, len(DAYS))
    cloudy = rng.random(len(DAYS)) < 0.3
    obs = np.where(cloudy, ndvi - rng.uniform(0.1, 0.3, len(DAYS)), ndvi)      # clouds depress NDVI
    true_green = float(np.trapezoid(np.maximum(ndvi - CURVE.base, 0), DAYS))
    yld = max(0.2, 0.05 + 0.040 * true_green + rng.normal(0, 0.12))
    return NDVISeries(pid, "teff", DAYS.copy(), obs, cloudy), yld


def main() -> int:
    try:
        rng = np.random.default_rng(8)
        hist = []
        for i in range(600):
            stress = rng.random() < 0.25
            s, y = simulate_plot(rng, f"H{i}", rng.normal(1.0, 0.15), rng.uniform(30, 90) if stress else None, rng.uniform(0.05, 0.25))
            hist.append((s, y))
        print(f"== 1. {len(hist)} historical plot-seasons, mean yield {np.mean([y for _, y in hist]):.2f} t/ha")

        cur, truth, areas = [], [], []
        for i in range(60):
            pest = i < 6
            s, y = simulate_plot(rng, f"P-{i:03d}", rng.normal(1.0, 0.12), 45 if pest else None, 0.22)
            cur.append(s); truth.append(y); areas.append(rng.uniform(0.2, 0.9))
        areas = np.array(areas)
        true_total = float(np.sum(np.array(truth) * areas))
        print(f"  current season: 60 plots, {areas.sum():.1f} ha, true production {true_total:.1f} t (unknown to the model)")

        alerts = detect_alerts(cur, CURVE, as_of_day=70)
        print(f"\n== 2. Alerts at day 70: {len(alerts)}")
        for a in alerts[:6]:
            print(f"  {a.plot_id} {a.severity:7s} z {a.z_score:5.2f}  {a.cause_hint}")

        print("\n== 3. Forecasts (cluster production, t)")
        fdays = [40, 55, 70, 85, 100]
        lin = []
        for day in fdays:
            Xh = np.array([features(s, day) for s, _ in hist]); yh = np.array([y for _, y in hist])
            coef, sd = fit_linear(Xh, yh)
            Xc = np.array([features(s, day) for s in cur])
            lin.append(forecast_linear(coef, sd, Xc, areas))
            print(f"  day {day:3d} linear: {lin[-1][0]:6.1f} t (80% {lin[-1][1]:.1f} to {lin[-1][2]:.1f})")

        deep = None
        try:
            from monitoring.deep import predict_mc, resample, train
            day = 85
            Xh = np.array([resample(*clean_and_smooth(s, day), day) for s, _ in hist]); yh = np.array([y for _, y in hist])
            model = train(Xh, yh, epochs=150)
            Xc = np.array([resample(*clean_and_smooth(s, day), day) for s in cur])
            mu, sdv = predict_mc(model, Xc)
            deep = {"day": day, "total": float(np.sum(mu * areas)), "plot_sd_mean": float(sdv.mean())}
            print(f"  day {day:3d} PyTorch 1D-CNN: {deep['total']:6.1f} t (mean plot MC-dropout sd {deep['plot_sd_mean']:.2f} t/ha)")
        except ImportError:
            print("  PyTorch not installed: deep model skipped")

        # chart data: one pest plot and one healthy plot, expected band
        g, sm_p = clean_and_smooth(cur[0], 140)
        _, sm_h = clean_and_smooth(cur[30], 140)
        sel = g[::5]
        exp = CURVE.expected(sel)
        out = {
            "days": [int(x) for x in sel],
            "pest": [round(float(v), 3) for v in sm_p[::5]], "healthy": [round(float(v), 3) for v in sm_h[::5]],
            "low": [round(float(v - 1.5 * CURVE.sd), 3) for v in exp], "high": [round(float(v + 1.5 * CURVE.sd), 3) for v in exp],
            "forecast_days": fdays, "lin": [[round(x, 1) for x in t] for t in lin], "true_total": round(true_total, 1),
            "deep": deep, "alerts": [a.__dict__ for a in alerts], "plots": 60, "area_ha": round(float(areas.sum()), 1),
        }
        path = ROOT / "assets" / "demo-monitoring.json"
        path.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"  [DEBUG] wrote {path.relative_to(ROOT)}")
        return 0
    except (KeyError, ValueError) as e:
        print(f"[DATA ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
End-to-end demo for Stage 01 on SYNTHETIC data (no real farmer or field data).

  1. Assess one plot for teff, bread wheat and maize (rule-based, with uncertainty).
  2. Derive AHP weights from a pairwise matrix and check consistency.
  3. Assess a synthetic 64 x 64 landscape and write a class map (SVG).
  4. If PyTorch is installed: pre-train the deep model on the rule-based (weak) labels.

Run from the branch root:  python3 src/demo.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from land_intel import FactorObservation, Method, Plot, ahp_weights, assess_grid, assess_plot  # noqa: E402
from land_intel.factors import FACTORS, PROFILES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def synthetic_landscape(n: int = 64, seed: int = 7) -> dict[str, np.ndarray]:
    """A toy highland landscape (~16 km): high plateau and escarpment in the east, Vertisol valley in the south-west."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
    bumps = sum(a * np.sin(fx * np.pi * xx + px) * np.sin(fy * np.pi * yy + py)
                for a, fx, fy, px, py in rng.uniform([40, 1, 1, 0, 0], [120, 6, 6, 3, 3], (6, 5)))
    altitude = 1500 + 1300 * (0.6 * xx + 0.4 * (1 - yy)) + bumps
    gy, gx = np.gradient(altitude, 250.0)                        # 250 m cells (~16 km landscape)
    slope = np.hypot(gx, gy) * 100 + 22 * np.clip((xx - 0.82) / 0.1, 0, 1)  # escarpment in the east
    rain = 650 + 0.25 * (altitude - 1500) + rng.normal(0, 30, (n, n))
    temp = 28 - 0.0065 * (altitude - 1000)                       # lapse rate
    ph = 6.6 - 1.4 * np.clip((rain - 800) / 600, 0, 1) + rng.normal(0, 0.15, (n, n))  # wetter = more acidic
    drainage = np.where((xx < 0.35) & (yy > 0.6), 1.8, 4.2) + rng.normal(0, 0.2, (n, n))  # Vertisol valley
    depth = np.clip(120 - 2.5 * slope + rng.normal(0, 10, (n, n)), 10, 200)
    soc = np.clip(1.0 + 0.0008 * (altitude - 1500) + rng.normal(0, 0.2, (n, n)), 0.2, 4)
    return {"altitude_m": altitude, "slope_pct": slope, "rain_season_mm": rain, "temp_mean_c": temp,
            "soil_ph": ph, "drainage_class": drainage, "soil_depth_cm": depth, "soc_pct": soc}


def class_map_svg(ranks: dict[str, np.ndarray], path: Path, cell: int = 4) -> None:
    colours = {3: "#1a9641", 2: "#a6d96a", 1: "#fdae61", 0: "#d7191c", -1: "#bbbbbb"}
    crops = list(ranks)
    n = next(iter(ranks.values())).shape[0]
    pad, gap, top = 10, 24, 30
    w = pad * 2 + len(crops) * n * cell + (len(crops) - 1) * gap
    h = top + n * cell + 50
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Helvetica, Arial, sans-serif">',
             f'<rect width="{w}" height="{h}" fill="#fbfaf6"/>']
    for k, crop in enumerate(crops):
        x0 = pad + k * (n * cell + gap)
        parts.append(f'<text x="{x0 + n * cell / 2}" y="20" text-anchor="middle" font-size="13" font-weight="bold">{crop}</text>')
        r = ranks[crop]
        for i in range(n):           # run-length encode rows to keep the SVG small
            j = 0
            while j < n:
                v = int(r[i, j]); j0 = j
                while j < n and int(r[i, j]) == v:
                    j += 1
                parts.append(f'<rect x="{x0 + j0 * cell}" y="{top + i * cell}" width="{(j - j0) * cell}" height="{cell}" fill="{colours[v]}"/>')
    ly = top + n * cell + 22
    for idx, (lab, v) in enumerate([("S1", 3), ("S2", 2), ("S3", 1), ("N", 0)]):
        lx = pad + idx * 70
        parts.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" fill="{colours[v]}"/>'
                     f'<text x="{lx + 18}" y="{ly}" font-size="12">{lab}</text>')
    parts.append(f'<text x="{w - pad}" y="{ly}" font-size="11" text-anchor="end" fill="#666">synthetic landscape, AHP-WLC, v0.1</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def demo_plot() -> None:
    print("== 1. Single plot assessment ==")
    plot = Plot("PLOT-DEMO-001", holder_id="HH-0001", area_ha=0.6, kebele="Demo kebele", woreda="Demo woreda")
    values = {"altitude_m": (2350, 15), "slope_pct": (11, 2), "rain_season_mm": (980, 80),
              "temp_mean_c": (17.5, 0.8), "soil_ph": (5.3, 0.2), "drainage_class": (3.5, 0.3),
              "soil_depth_cm": (90, 15), "soc_pct": (1.9, 0.3)}
    for code, (v, sd) in values.items():
        plot.observe(FactorObservation(FACTORS[code], v, source="synthetic", std=sd))
    for crop, profile in PROFILES.items():
        for method in (Method.FAO_LIMITING, Method.AHP_WLC):
            a = assess_plot(plot, profile, method, n_monte_carlo=500)
            print("  " + a.summary())


def demo_ahp() -> None:
    print("\n== 2. AHP weights (rainfall, slope, temperature, soil pH, drainage) ==")
    pairwise = np.array([
        [1,   2,   2,   3,   3],
        [1/2, 1,   1,   2,   2],
        [1/2, 1,   1,   2,   2],
        [1/3, 1/2, 1/2, 1,   1],
        [1/3, 1/2, 1/2, 1,   1],
    ])
    w, cr = ahp_weights(pairwise)
    print("  weights:", np.round(w, 3), f"| CR = {cr:.3f}", "(acceptable)" if cr < 0.10 else "(REVISE judgements)")


def demo_grid() -> dict[str, np.ndarray]:
    print("\n== 3. Landscape assessment (64 x 64 synthetic cells) ==")
    layers = synthetic_landscape()
    ranks = {}
    for crop, profile in PROFILES.items():
        for method in (Method.FAO_LIMITING, Method.AHP_WLC):
            out = assess_grid(layers, profile, method)
            if method == Method.AHP_WLC:
                ranks[crop] = out["rank"]
            share = {lab: float((out["rank"] == v).mean()) for lab, v in [("S1", 3), ("S2", 2), ("S3", 1), ("N", 0)]}
            lim_codes, counts = np.unique(out["limiting"], return_counts=True)
            top = out["factor_codes"][int(lim_codes[np.argmax(counts)])]
            print(f"  {crop:12s} {method.name:12s} " + "  ".join(f"{k} {v:5.1%}" for k, v in share.items())
                  + f"  | most common limiting: {top}")
    svg = ROOT / "assets" / "demo-class-map.svg"
    class_map_svg(ranks, svg)
    print(f"  [DEBUG] wrote {svg.relative_to(ROOT)}")
    return {"layers": layers, "ranks": ranks}


def demo_deep(layers: dict[str, np.ndarray], ranks: dict[str, np.ndarray]) -> None:
    print("\n== 4. Deep model pre-training on rule-based labels ==")
    try:
        import torch
    except ImportError:
        print("  PyTorch not installed, skipping (pip install torch)")
        return
    from land_intel.model import MultiCropSuitabilityNet, multi_crop_loss, predict_with_uncertainty

    torch.manual_seed(0)
    x = np.stack([layers[c] for c in sorted(layers)])
    x = (x - x.mean(axis=(1, 2), keepdims=True)) / (x.std(axis=(1, 2), keepdims=True) + 1e-6)
    x = torch.tensor(x, dtype=torch.float32).unsqueeze(0)            # (1, C, 64, 64)
    y = {c: torch.tensor(r, dtype=torch.long).unsqueeze(0) for c, r in ranks.items()}
    model = MultiCropSuitabilityNet(in_channels=x.shape[1], crops=list(ranks), width=16)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    for step in range(1, 151):
        model.train()
        opt.zero_grad()
        loss = multi_crop_loss(model(x), y)
        if not torch.isfinite(loss):
            raise RuntimeError(f"Loss became {loss.item()} at step {step}")
        loss.backward()
        opt.step()
        if step in (1, 50, 100, 150):
            print(f"  [DEBUG] step {step:3d} loss {loss.item():.3f}")
    pred = predict_with_uncertainty(model, x, n_samples=10)
    for c in ranks:
        valid = y[c] >= 0
        acc = (pred[c]["class"][valid] == y[c][valid]).float().mean().item()
        print(f"  {c:12s} agreement with rule labels {acc:.1%} | mean confidence {pred[c]['confidence'].mean():.2f}")


def main() -> int:
    try:
        demo_plot()
        demo_ahp()
        g = demo_grid()
        demo_deep(g["layers"], g["ranks"])
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

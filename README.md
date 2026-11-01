# Stage 08: Monitoring, Forecasting & Risk

Branch: `stage/08-monitoring-risk`
Published at: https://land-suitability.github.io/stages/08-monitoring-risk/

This branch contains **only** the content for stage 08 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/08-monitoring-risk/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, monitoring methods, Amhara context, data, interactive growth-curve and forecast charts, alerts, outputs, validation, roadmap |
| `src/monitoring/` | Python package: domain model, NDVI cleaning and smoothing, anomaly alerts with cause hints, linear yield forecast, PyTorch 1D-CNN with MC dropout |
| `src/demo.py` | Pest-outbreak demo on synthetic NDVI series (writes assets/demo-monitoring.json) |
| `tests/test_monitoring.py` | Unit tests |

```bash
pip install numpy torch     # torch is optional; the deep model is skipped without it
python3 src/demo.py
python3 tests/test_monitoring.py
```

Alert thresholds (watch below -1.5, warning below -2.75) are calibrated per crop from past seasons. The deep model is kept only if it beats the linear baseline on held-out seasons.

## Rules

- `index.html` at the branch root is the stage's landing page. Keep it.
- Link shared styling from the hub with absolute paths: `/assets/css/site.css`, `/assets/js/site.js`.
- Put stage-specific files (pages, images, data, notebooks) in this branch. Use relative links between them.
- Do not change shared styling, the hub page or `stages.json` here. Those live on the hub branch (`main`).
- Pushing to this branch triggers `.github/workflows/notify-hub.yml`, which rebuilds the whole site.

## Suggested layout

```
index.html        landing page for the stage
docs/             further pages (methods, domain model, protocols)
assets/           images and figures for this stage
data/             small public sample data (no personal farmer data)
src/              analysis or model code for this stage
```

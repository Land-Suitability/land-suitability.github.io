# Stage 04: Crop Selection & Production Planning

Branch: `stage/04-crop-planning`
Published at: https://land-suitability.github.io/stages/04-crop-planning/

This branch contains **only** the content for stage 04 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/04-crop-planning/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, planner method, Amhara context, data, interactive plan chart, shadow prices, outputs, validation, roadmap |
| `src/crop_plan/` | Python package: domain model and the market-backwards linear programme (HiGHS via scipy) |
| `src/demo.py` | Three-cluster, two-season demo (writes assets/demo-plan.json) |
| `tests/test_planner.py` | Unit tests |

```bash
pip install numpy scipy
python3 src/demo.py
python3 tests/test_planner.py
```

Prices, costs and yields in the demo are illustrative. Water enters as twelve monthly constraints per cluster (see stage 02).

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

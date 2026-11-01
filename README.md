# Stage 12: Market Distribution & Customer Network

Branch: `stage/12-market-distribution`
Published at: https://land-suitability.github.io/stages/12-market-distribution/

This branch contains **only** the content for stage 12 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/12-market-distribution/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, settlement/payment/impact/learning methods, Amhara context, data, settlement table, interactive impact and yield-check charts, outputs, validation, roadmap |
| `src/distribution/` | Python package: domain model, settlement with premiums and deductions, household payments via lot traceability, payment timeliness, difference-in-differences, yields by class |
| `src/demo.py` | Deliveries, payments, impact and learning demo (writes assets/demo-distribution.json) |
| `tests/test_distribution.py` | Unit tests |

```bash
pip install numpy
python3 src/demo.py
python3 tests/test_distribution.py
```

Household data are pseudonymous and never published. Comparison kebeles must be chosen at baseline, before the pilot starts.

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

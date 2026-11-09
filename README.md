# Stage 01: Land Intelligence & Suitability

Branch: `stage/01-land-intelligence`
Published at: https://land-suitability.github.io/stages/01-land-intelligence/

This branch contains **only** the content for stage 01 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/01-land-intelligence/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, methods, crop requirements, Amhara context, data, demo, outputs, validation, roadmap |
| `docs/methodology.html` | Method details and an interactive AHP weighting calculator |
| `src/land_intel/` | Python package: domain model, factor catalogue, scoring engine, PyTorch model |
| `src/demo.py` | End-to-end demo on a synthetic landscape (writes `assets/demo-class-map.svg`) |
| `tests/test_scoring.py` | Unit tests for the scoring engine |
| `availability/index.html` | Phase 1, module 1a: land availability page (statuses, rules, demo maps, calculator) |
| `src/land_intel/availability.py` | Land availability domain model and rules |
| `src/demo_availability.py` | Availability demo on the same landscape (writes `assets/availability-maps.svg`, `assets/demo-availability.json`) |
| `tests/test_availability.py` | Unit tests for every availability rule |

```bash
pip install numpy torch        # torch is optional; the demo skips the deep model without it
python3 src/demo.py
python3 tests/test_scoring.py  # or: python3 -m pytest tests
python3 src/demo_availability.py
python3 tests/test_availability.py
```

Crop requirement thresholds in `src/land_intel/factors.py` are **indicative** and must be
calibrated with regional research institutes and local trials before use with farmers.

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

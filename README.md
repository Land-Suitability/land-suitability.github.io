# Stage 03: Climate & Seasonal Intelligence

Branch: `stage/03-climate-intelligence`
Published at: https://land-suitability.github.io/stages/03-climate-intelligence/

This branch contains **only** the content for stage 03 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/03-climate-intelligence/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, onset/end/risk methods, Amhara context, data, interactive charts, outputs, validation, roadmap |
| `src/climate_intel/` | Python package: domain model, season analytics (onset, end, dry spells, frost, SPI, outlook), synthetic weather generator |
| `src/demo.py` | 30-year synthetic demo (writes assets/demo-climate.json) |
| `tests/test_climate.py` | Unit tests, including false-start rejection |

```bash
pip install numpy scipy
python3 src/demo.py
python3 tests/test_climate.py
```

Onset thresholds are a common agro-climatic definition and must be agreed per location with agronomists and farmers.

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

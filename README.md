# Stage 09: Harvest & Post-harvest Management

Branch: `stage/09-harvest-postharvest`
Published at: https://land-suitability.github.io/stages/09-harvest-postharvest/

This branch contains **only** the content for stage 09 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/09-harvest-postharvest/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, scheduling/loss/drying/grading methods, Amhara context, data, interactive loss and grade charts, lot table, outputs, validation, roadmap |
| `src/harvest/` | Python package: domain model, EDF/FIFO harvest scheduling, field loss model, drying, grading, traceable lot formation with quality segregation |
| `src/demo.py` | Cluster A teff harvest demo (writes assets/demo-harvest.json) |
| `tests/test_harvest.py` | Unit tests |

```bash
pip install numpy
python3 src/demo.py
python3 tests/test_harvest.py
```

Loss rates and grade limits are indicative; use measured losses and the buyer's contract grades.

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

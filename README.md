# Stage 10: Storage, Processing & Aggregation

Branch: `stage/10-storage-aggregation`
Published at: https://land-suitability.github.io/stages/10-storage-aggregation/

This branch contains **only** the content for stage 10 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/10-storage-aggregation/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, location/storage/inventory methods, Amhara context, data, interactive store-or-sell and stock charts, outputs, validation, roadmap |
| `src/storage/` | Python package: domain model, capacitated p-median centre location, store-or-sell valuation, inventory simulation, warehouse receipts |
| `src/demo.py` | 30-kebele demo (writes assets/demo-storage.json) |
| `tests/test_storage.py` | Unit tests |

```bash
pip install numpy
python3 src/demo.py
python3 tests/test_storage.py
```

Storage loss rates and costs are indicative; measure them per technology in the pilot stores.

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

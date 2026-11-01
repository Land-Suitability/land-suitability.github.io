# Stage 11: Logistics & Transportation

Branch: `stage/11-logistics-transport`
Published at: https://land-suitability.github.io/stages/11-logistics-transport/

This branch contains **only** the content for stage 11 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/11-logistics-transport/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, routing methods, Amhara context, data, interactive cost charts, outputs, validation, roadmap |
| `src/logistics/` | Python package: road network with surfaces and rainy-season closures, Dijkstra, Clarke-Wright savings routes |
| `src/demo.py` | 12-kebele collection demo (writes assets/demo-logistics.json) |
| `tests/test_logistics.py` | Unit tests |

```bash
python3 src/demo.py          # standard library only
python3 tests/test_logistics.py
```

Road distances, surfaces and closures in the demo are made up. Use OpenStreetMap plus field checks for the pilot network.

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

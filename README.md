# Stage 02: Water Resource Assessment

Branch: `stage/02-water-resources`
Published at: https://land-suitability.github.io/stages/02-water-resources/

This branch contains **only** the content for stage 02 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/02-water-resources/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, methods, Amhara context, data, interactive water-budget chart, outputs, validation, roadmap |
| `src/water_res/` | Python package: domain model, FAO-56 hydrology (Ra, Hargreaves ET0, Kc, effective rain), monthly budget |
| `src/demo.py` | Synthetic lake-shore cluster demo (writes `assets/demo-water-budget.json` for the chart) |
| `tests/test_water.py` | Unit tests, including FAO-56 Example 8 |
| `water-availability/index.html` | Phase 1, module 2: water availability mapping page (maps, access classes, calculator) |
| `src/water_res/mapping.py` | Streams and monthly flow (fill, D8), groundwater potential, water points, water access per field |
| `src/water_res/handoff.py` | Reads and checks module 1's hand-off (`data/handoff-module1.json`) |
| `src/demo_water_map.py` | Mapping demo on module 1's landscape (writes `assets/water-maps.svg`, `assets/demo-water-availability.json`) |
| `tests/test_mapping.py` | Unit tests for the mapping rules |

```bash
pip install numpy scipy        # scipy is optional; it is used for the crop-mix optimisation step
python3 src/demo.py
python3 tests/test_water.py    # or: python3 -m pytest tests
python3 src/demo_water_map.py
python3 tests/test_mapping.py
```

Key design decision: the water budget passed to stage 04 is **twelve monthly limits**, not one
seasonal total, because the lean dry-season month usually decides the irrigable area.
Groundwater supply always needs field hydrogeology; satellite data alone cannot establish it.

Phase 1 hand-off: `data/handoff-module1.json` is a copy of stage 01's
`assets/handoff-available-land.json` with the source commit recorded under `provenance`. Refresh it
when module 1 changes; the loader rejects an unknown contract or version.

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

# Stage 06: Input & Resource Coordination

Branch: `stage/06-input-coordination`
Published at: https://land-suitability.github.io/stages/06-input-coordination/

This branch contains **only** the content for stage 06 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/06-input-coordination/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, scheduling methods, Amhara context, data, interactive on-time and order charts, warnings, outputs, validation, roadmap |
| `src/inputs/` | Python package: domain model, plan explosion, lognormal lead times, order-by dates, supplier allocation with warnings |
| `src/demo.py` | Input orders for the stage 04 demo plan (writes assets/demo-inputs.json) |
| `tests/test_inputs.py` | Unit tests |

```bash
python3 src/demo.py          # standard library only
python3 tests/test_inputs.py
```

Input rates are indicative placeholders; use regional recommendations. Supplier names and prices in the demo are made up.

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

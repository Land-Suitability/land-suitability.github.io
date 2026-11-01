# Stage 07: Farm Implementation & Production

Branch: `stage/07-farm-production`
Published at: https://land-suitability.github.io/stages/07-farm-production/

This branch contains **only** the content for stage 07 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/07-farm-production/`.

## What is here (v0.1)

| Path | Content |
|---|---|
| `index.html` | Stage page: purpose, domain model, assignment/calendar/adherence/visit methods, Amhara context, data, interactive adherence and workload charts, outputs, validation, roadmap |
| `src/farm_ops/` | Python package: domain model, comparative-advantage plot assignment, operations calendar, adherence, visit prioritisation |
| `src/demo.py` | Cluster A Meher demo with synthetic households (writes assets/demo-farm.json) |
| `tests/test_farm.py` | Unit tests |

```bash
pip install numpy
python3 src/demo.py
python3 tests/test_farm.py
```

Households are identified only by pseudonymous IDs. Never commit names, phone numbers or exact plot coordinates of real farmers.

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

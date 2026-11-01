# Stage 05: Market Intelligence & Demand Forecasting

Branch: `stage/05-market-intelligence`
Published at: https://land-suitability.github.io/stages/05-market-intelligence/

This branch contains **only** the content for stage 05 of the
Amhara Integrated Agriculture Ecosystem operating chain. Everything at the root of this branch is
published under `/stages/05-market-intelligence/`.

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

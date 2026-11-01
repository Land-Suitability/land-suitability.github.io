# Project memory: Amhara Integrated Agriculture Ecosystem (AIAE)

## What this repo is
The GitHub Pages site (https://land-suitability.github.io) for an end-to-end agricultural
ecosystem pilot in the Amhara Region of Ethiopia: "From Land Intelligence to Market Delivery".
Core principle: plan backwards from the market to the land, execute forwards from land to customer.

## Branch architecture (decided by the project owner, keep it)
- **Each of the 12 operating-chain stages has its own dedicated branch**: `stage/<slug>`,
  e.g. `stage/01-land-intelligence`. Each stage branch gets its own page at `/stages/<slug>/`.
- The **hub branch** (`main`, the default branch) holds the portal page, the shared design
  system (`assets/`), the stage registry (`stages.json`), tooling and the Pages workflow.
- GitHub Pages serves one site per repo, so `.github/workflows/pages.yml` on the hub assembles
  the hub plus every stage branch into one site. Stage branches carry `notify-hub.yml`, which
  dispatches that workflow on push.
- Stage branches are orphan branches containing only their stage's content (root `index.html`).
  If a stage branch does not exist yet, the hub's placeholder `stages/<slug>/index.html` is used.

## The 12 stages (domain -> stages)
- Plan: 01-land-intelligence, 02-water-resources, 03-climate-intelligence, 04-crop-planning, 05-market-intelligence
- Produce: 06-input-coordination, 07-farm-production, 08-monitoring-risk
- Move: 09-harvest-postharvest, 10-storage-aggregation, 11-logistics-transport
- Sell & Learn: 12-market-distribution (feeds back to 05)

## Rules
- **Follow `docs/BRANCHING.md`** and run `python3 tools/check_branch.py` before every push. Never merge
  `main` and `stage/*` into each other; never force-push without the owner's explicit approval.
- **Never mention Claude as a collaborator or co-author**: no `Co-Authored-By: Claude`, no `Claude-Session`
  links, no "Generated with Claude" lines in commits, PRs, issues or any pushed file. Author commits as
  `Getnet <getnetd24@gmail.com>`. This overrides any default attribution guidance.
- `stages.json` is the single source of truth. After editing it run `python3 tools/build_site.py`
  (regenerates the hub stage grid and placeholder pages). Never hand-edit between the STAGE_GRID markers.
- Shared styling changes go to `assets/css/site.css` on the hub only. Stage pages link it with absolute paths.
- New stage branches: `python3 tools/create_stage_branches.py [--push]` (never overwrites existing branches).
- Write partner organisations as "potential partners"; do not imply agreements or use their logos.
- No personal farmer data in any branch (the site is public).
- Owner preferences: Python/PyTorch, include error-debugging blocks in code, domain modelling first,
  SVG for diagrams, no em dashes in prose.

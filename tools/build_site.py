#!/usr/bin/env python3
"""
Build the hub's generated parts from the single source of truth, stages.json.

What it does
  1. Validates stages.json (unique numbers/slugs, valid domains, valid upstream/downstream links).
  2. Renders the 12-stage grid into index.html between the STAGE_GRID markers.
  3. Renders placeholder pages at stages/<slug>/index.html from templates/stage.html.

The placeholder pages are a fallback. When a stage branch (stage/<slug>) exists, the
Pages workflow publishes that branch's content at /stages/<slug>/ instead.

Usage
  python3 tools/build_site.py            # build everything
  python3 tools/build_site.py --check    # validate only, write nothing
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES_JSON = ROOT / "stages.json"
TEMPLATE = ROOT / "templates" / "stage.html"
INDEX = ROOT / "index.html"
GRID_START = re.compile(r"<!-- STAGE_GRID:START.*?-->")
GRID_END = "<!-- STAGE_GRID:END -->"


# ------------------------------------------------------------------ domain model
@dataclass(frozen=True)
class Domain:
    id: str
    title: str
    question: str


@dataclass(frozen=True)
class Stage:
    number: int
    slug: str
    title: str
    domain: str
    summary: str
    questions: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    kpis: list[str] = field(default_factory=list)
    upstream: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)
    status: str = "skeleton"         # e.g. "skeleton", "v0.1" (methodology, demo and tests on the stage branch)

    @property
    def padded(self) -> str:
        return f"{self.number:02d}"

    def branch(self, prefix: str) -> str:
        return f"{prefix}{self.slug}"

    @property
    def url(self) -> str:
        return f"/stages/{self.slug}/"


class ConfigError(ValueError):
    """Raised when stages.json is inconsistent."""


def load_config() -> tuple[dict, list[Domain], list[Stage]]:
    if not STAGES_JSON.exists():
        raise ConfigError(f"Missing {STAGES_JSON}")
    try:
        raw = json.loads(STAGES_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"stages.json is not valid JSON (line {e.lineno}, col {e.colno}): {e.msg}") from e

    project = raw["project"]
    domains = [Domain(**d) for d in raw["domains"]]
    try:
        stages = [Stage(**s) for s in raw["stages"]]
    except TypeError as e:
        raise ConfigError(f"Unexpected or missing field in a stage entry: {e}") from e
    validate(domains, stages)
    return project, domains, sorted(stages, key=lambda s: s.number)


def validate(domains: list[Domain], stages: list[Stage]) -> None:
    errors: list[str] = []
    domain_ids = {d.id for d in domains}
    slugs = [s.slug for s in stages]
    numbers = [s.number for s in stages]

    if len(set(slugs)) != len(slugs):
        errors.append(f"Duplicate slugs: {sorted({x for x in slugs if slugs.count(x) > 1})}")
    if sorted(numbers) != list(range(1, len(stages) + 1)):
        errors.append(f"Stage numbers must be 1..{len(stages)} without gaps, got {sorted(numbers)}")
    for s in stages:
        if not re.fullmatch(r"\d{2}-[a-z0-9-]+", s.slug):
            errors.append(f"Stage {s.number}: slug '{s.slug}' must look like 'NN-lowercase-words'")
        if not s.slug.startswith(s.padded):
            errors.append(f"Stage {s.number}: slug '{s.slug}' must start with '{s.padded}'")
        if s.domain not in domain_ids:
            errors.append(f"Stage {s.number}: unknown domain '{s.domain}'")
        for ref in s.upstream + s.downstream:
            if ref not in slugs:
                errors.append(f"Stage {s.number}: link to unknown stage '{ref}'")
            if ref == s.slug:
                errors.append(f"Stage {s.number}: stage links to itself")
    if errors:
        raise ConfigError("stages.json validation failed:\n  - " + "\n  - ".join(errors))


# ------------------------------------------------------------------ rendering
def esc(text: str) -> str:
    return html.escape(text, quote=True)


def li(items: list[str]) -> str:
    return "".join(f"<li>{esc(i)}</li>" for i in items) or "<li>To be defined</li>"


def chips(refs: list[str], by_slug: dict[str, Stage], empty: str) -> str:
    if not refs:
        return f'<span class="chip">{esc(empty)}</span>'
    return "".join(
        f'<a class="chip" href="{by_slug[r].url}">{by_slug[r].padded}. {esc(by_slug[r].title)}</a>' for r in refs
    )


def render_grid(domains: list[Domain], stages: list[Stage], prefix: str) -> str:
    parts = []
    for d in domains:
        cards = []
        for s in (x for x in stages if x.domain == d.id):
            cards.append(
                f'        <a class="card stage-card" href="{s.url}">\n'
                f'          <span class="stage-num">Stage {s.padded} <span class="status">{esc(s.status)}</span></span>\n'
                f'          <h3>{esc(s.title)}</h3>\n'
                f'          <p>{esc(s.summary)}</p>\n'
                f'          <span class="branch">{esc(s.branch(prefix))}</span>\n'
                f'        </a>'
            )
        parts.append(
            f'      <div class="domain d-{d.id}">\n'
            f'        <div class="domain-head"><span class="pill">{esc(d.title)}</span>'
            f'<p>{esc(d.question)}</p></div>\n'
            f'        <div class="grid cols-3">\n' + "\n".join(cards) + "\n        </div>\n"
            f'      </div>'
        )
    return "\n".join(parts)


def render_stage(tpl: str, project: dict, domains: list[Domain], stages: list[Stage], s: Stage) -> str:
    by_slug = {x.slug: x for x in stages}
    dom = next(d for d in domains if d.id == s.domain)
    idx = stages.index(s)
    prev_link = (f'<a class="btn" href="{stages[idx - 1].url}">&larr; {stages[idx - 1].padded}. '
                 f'{esc(stages[idx - 1].title)}</a>') if idx > 0 else "<span></span>"
    next_link = (f'<a class="btn" href="{stages[idx + 1].url}">{stages[idx + 1].padded}. '
                 f'{esc(stages[idx + 1].title)} &rarr;</a>') if idx < len(stages) - 1 else "<span></span>"
    values = {
        "project_name": esc(project["name"]),
        "project_short": esc(project["short_name"]),
        "tagline": esc(project["tagline"]),
        "title": esc(s.title),
        "summary": esc(s.summary),
        "number_padded": s.padded,
        "slug": s.slug,
        "branch": esc(s.branch(project["stage_branch_prefix"])),
        "domain_id": dom.id,
        "domain_title": esc(dom.title),
        "questions": li(s.questions),
        "components": li(s.components),
        "data_sources": li(s.data_sources),
        "outputs": li(s.outputs),
        "kpis": li(s.kpis),
        "upstream_chips": chips(s.upstream, by_slug, "Entry point"),
        "downstream_chips": chips(s.downstream, by_slug, "End of chain"),
        "prev_link": prev_link,
        "next_link": next_link,
    }
    out = tpl
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", val)
    leftover = re.findall(r"\{\{(\w+)\}\}", out)
    if leftover:
        raise ConfigError(f"Template placeholders not filled for stage {s.slug}: {sorted(set(leftover))}")
    return out


def inject_grid(grid_html: str) -> None:
    text = INDEX.read_text(encoding="utf-8")
    m = GRID_START.search(text)
    end = text.find(GRID_END)
    if not m or end == -1 or end < m.end():
        raise ConfigError("index.html is missing the STAGE_GRID:START / STAGE_GRID:END markers")
    new = text[: m.end()] + "\n" + grid_html + "\n" + text[end:]
    INDEX.write_text(new, encoding="utf-8")


# ------------------------------------------------------------------ entry point
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate stages.json only")
    args = parser.parse_args()
    try:
        project, domains, stages = load_config()
        print(f"[OK] stages.json valid: {len(stages)} stages in {len(domains)} domains")
        if args.check:
            return 0

        prefix = project["stage_branch_prefix"]
        inject_grid(render_grid(domains, stages, prefix))
        print("[OK] index.html stage grid updated")

        tpl = TEMPLATE.read_text(encoding="utf-8")
        for s in stages:
            target = ROOT / "stages" / s.slug / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render_stage(tpl, project, domains, stages, s), encoding="utf-8")
            print(f"[DEBUG] wrote {target.relative_to(ROOT)}")
        return 0
    except ConfigError as e:
        print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        return 1
    except Exception as e:  # unexpected: show full traceback for debugging
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

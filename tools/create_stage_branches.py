#!/usr/bin/env python3
"""
Create one orphan branch per stage (stage/<slug>) seeded from the hub's placeholder page.

Each new branch contains only:
  index.html                          (copied from stages/<slug>/index.html)
  README.md                           (rendered from templates/stage-branch/README.md)
  .github/workflows/notify-hub.yml    (asks the hub to rebuild Pages on every push)

Branches are built with git plumbing (temporary index), so your working tree and
current branch are never touched. Existing branches are skipped, never overwritten.

Usage
  python3 tools/build_site.py                      # make sure placeholders are current
  python3 tools/create_stage_branches.py           # create branches locally (dry-run listing first)
  python3 tools/create_stage_branches.py --push    # create and push them to origin
  python3 tools/create_stage_branches.py --only 01-land-intelligence --push
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import ROOT, ConfigError, load_config  # noqa: E402

BRANCH_TEMPLATE = ROOT / "templates" / "stage-branch"


def git(*args: str, env: dict | None = None, input_bytes: bytes | None = None) -> str:
    res = subprocess.run(["git", *args], cwd=ROOT, env=env, input=input_bytes,
                         capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{res.stderr.decode(errors='replace')}")
    return res.stdout.decode().strip()


def branch_exists(branch: str) -> tuple[bool, bool]:
    local = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=ROOT).returncode == 0
    remote_out = subprocess.run(["git", "ls-remote", "--heads", "origin", branch], cwd=ROOT,
                                capture_output=True, text=True)
    remote = bool(remote_out.stdout.strip())
    return local, remote


def render(text: str, values: dict[str, str]) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def build_orphan_commit(files: dict[str, bytes], message: str) -> str:
    """Write files into a temporary index and return a parentless commit SHA."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        for path, content in files.items():
            sha = git("hash-object", "-w", "--stdin", input_bytes=content)
            git("update-index", "--add", "--cacheinfo", f"100644,{sha},{path}", env=env)
        tree = git("write-tree", env=env)
    return git("commit-tree", tree, "-m", message)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--push", action="store_true", help="push created branches to origin")
    ap.add_argument("--only", nargs="*", default=None, help="limit to these stage slugs")
    args = ap.parse_args()
    try:
        project, _domains, stages = load_config()
        prefix = project["stage_branch_prefix"]
        if args.only:
            unknown = set(args.only) - {s.slug for s in stages}
            if unknown:
                raise ConfigError(f"Unknown stage slugs: {sorted(unknown)}")
            stages = [s for s in stages if s.slug in args.only]

        readme_tpl = (BRANCH_TEMPLATE / "README.md").read_text(encoding="utf-8")
        notify = (BRANCH_TEMPLATE / ".github" / "workflows" / "notify-hub.yml").read_bytes()
        created: list[str] = []

        for s in stages:
            branch = s.branch(prefix)
            local, remote = branch_exists(branch)
            if local or remote:
                where = " and ".join(w for w, ok in (("local", local), ("remote", remote)) if ok)
                print(f"[SKIP] {branch} already exists ({where})")
                continue
            page = ROOT / "stages" / s.slug / "index.html"
            if not page.exists():
                raise ConfigError(f"{page.relative_to(ROOT)} missing. Run tools/build_site.py first.")
            readme = render(readme_tpl, {
                "number_padded": s.padded, "title": s.title, "branch": branch, "slug": s.slug,
                "site_url": project["site_url"], "project_name": project["name"],
            })
            files = {
                "index.html": page.read_bytes(),
                "README.md": readme.encode(),
                ".github/workflows/notify-hub.yml": notify,
            }
            commit = build_orphan_commit(files, f"Initialise stage {s.padded}: {s.title}")
            git("update-ref", f"refs/heads/{branch}", commit)
            created.append(branch)
            print(f"[OK] created {branch} at {commit[:8]}")

        if args.push and created:
            for b in created:
                git("push", "-u", "origin", b)
                print(f"[OK] pushed {b}")
        elif created:
            print("\nBranches created locally only. Re-run with --push, or: git push -u origin <branch>")
        return 0
    except ConfigError as e:
        print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

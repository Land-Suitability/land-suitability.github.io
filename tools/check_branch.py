#!/usr/bin/env python3
"""
Pre-push checker for the branch rules in docs/BRANCHING.md.

Run it in your clone before every push, on any branch:

    # on main (the hub)
    python3 tools/check_branch.py

    # on a stage branch (the script lives on main, so fetch it first)
    git fetch origin main
    git show origin/main:tools/check_branch.py > /tmp/check_branch.py
    python3 /tmp/check_branch.py

Exit code 0 = all rules pass, 1 = at least one rule failed (details are printed).
It only reads; it never changes files, commits or pushes.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import traceback

HUB = "main"
STAGE_PREFIX = "stage/"
AUTHOR_EMAIL = "getnetd24@gmail.com"
FORBIDDEN_TRAILERS = re.compile(r"co-authored-by:\s*claude|claude-session|generated with \[?claude", re.I)
HUB_ONLY_PATHS = ("assets/css/site.css", "assets/js/site.js", "stages.json", ".github/workflows/pages.yml",
                  "tools/", "templates/")
MAX_FILE_MB = 5
PHONE = re.compile(r"(\+?251|0)9\d{8}\b")          # Ethiopian mobile numbers: must never be published


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def ok(self, msg: str) -> None:
        print(f"  [PASS] {msg}")

    def fail(self, msg: str) -> None:
        self.failures.append(msg)
        print(f"  [FAIL] {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  [WARN] {msg}")


def git(*args: str, check: bool = True) -> str:
    res = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout.strip()


def outgoing_commits(branch: str) -> list[str]:
    """Commits on this branch that are not yet on its remote counterpart (all commits if it is new)."""
    remote = f"origin/{branch}"
    has_remote = git("rev-parse", "--verify", "--quiet", remote, check=False)
    rng = f"{remote}..HEAD" if has_remote else "HEAD"
    out = git("rev-list", rng)
    return out.split() if out else []


def check_common(branch: str, r: Report) -> None:
    print("\n== Common rules")
    if git("status", "--porcelain"):
        r.warn("Uncommitted changes in the working tree (commit or stash them before pushing)")
    else:
        r.ok("Working tree clean")

    commits = outgoing_commits(branch)
    print(f"  [DEBUG] {len(commits)} outgoing commit(s)")
    n_before = len(r.failures)
    for c in commits:
        email = git("log", "-1", "--format=%ae", c)
        body = git("log", "-1", "--format=%B", c)
        subject = body.splitlines()[0] if body else c[:8]
        if email != AUTHOR_EMAIL:
            r.fail(f"{c[:8]} '{subject}' authored by {email}, expected {AUTHOR_EMAIL}")
        if FORBIDDEN_TRAILERS.search(body):
            r.fail(f"{c[:8]} '{subject}' contains a forbidden attribution line (see Rule 6)")
    if commits and len(r.failures) == n_before:
        r.ok("Outgoing commits: correct author, no forbidden attribution lines")

    for path in git("ls-files").splitlines():
        try:
            size_mb = int(git("cat-file", "-s", f"HEAD:{path}", check=False) or 0) / 1e6
        except ValueError:
            continue
        if size_mb > MAX_FILE_MB:
            r.fail(f"{path} is {size_mb:.1f} MB (limit {MAX_FILE_MB} MB; keep large data out of git)")
        if path.endswith((".html", ".json", ".csv", ".md", ".py", ".txt")):
            text = git("show", f"HEAD:{path}", check=False)
            if PHONE.search(text):
                r.fail(f"{path} contains something that looks like a phone number (no personal data, Rule 7)")


def check_hub(r: Report) -> None:
    print("\n== Hub rules (main)")
    res = subprocess.run([sys.executable, "tools/build_site.py", "--check"], capture_output=True, text=True)
    (r.ok if res.returncode == 0 else r.fail)(f"stages.json validation: {(res.stdout or res.stderr).strip().splitlines()[-1]}")

    # the generated grid and placeholders must match stages.json
    res = subprocess.run([sys.executable, "tools/build_site.py"], capture_output=True, text=True)
    if res.returncode != 0:
        r.fail(f"build_site.py failed: {res.stderr.strip()}")
        return
    drift = git("status", "--porcelain", "index.html", "stages/")
    if drift:
        r.fail("index.html or stages/ placeholders were out of date with stages.json; build_site.py has now "
               "regenerated them, review and commit:\n      " + drift.replace("\n", "\n      "))
    else:
        r.ok("Stage grid and placeholders are in sync with stages.json")

    for f in ("CLAUDE.md", "docs/BRANCHING.md", ".github/workflows/pages.yml", "templates/stage-branch/.github/workflows/notify-hub.yml"):
        (r.ok if git("ls-files", f) else r.fail)(f"{f} present")


def check_stage(branch: str, r: Report) -> None:
    slug = branch[len(STAGE_PREFIX):]
    print(f"\n== Stage rules ({branch})")
    try:
        registry = json.loads(git("show", f"origin/{HUB}:stages.json"))
    except (RuntimeError, json.JSONDecodeError) as e:
        r.fail(f"Could not read stages.json from origin/{HUB} (run 'git fetch origin {HUB}'): {e}")
        return
    slugs = [s["slug"] for s in registry["stages"]]
    (r.ok if slug in slugs else r.fail)(f"slug '{slug}' is registered in stages.json on {HUB}")

    files = git("ls-files").splitlines()
    (r.ok if "index.html" in files else r.fail)("index.html exists at the branch root")
    (r.ok if ".github/workflows/notify-hub.yml" in files else r.fail)("notify-hub.yml present (triggers the site rebuild)")
    hub_files = [f for f in files if any(f == p or (p.endswith("/") and f.startswith(p)) for p in HUB_ONLY_PATHS)]
    if hub_files:
        r.fail(f"hub-only files found on a stage branch (they belong on {HUB}): {hub_files}")
    else:
        r.ok("no hub-only files on this stage branch")

    if "index.html" in files:
        page = git("show", "HEAD:index.html")
        (r.ok if 'href="/assets/css/site.css"' in page else r.fail)("index.html links the shared stylesheet /assets/css/site.css")
        bad = re.findall(r'(?:href|src)="(?!https?:|/|#|mailto:)([^"]*\.\./\.\./[^"]*)"', page)
        if bad:
            r.warn(f"relative links that climb out of the stage folder: {bad[:3]} (use /absolute paths for other stages)")
    if git("merge-base", "HEAD", f"origin/{HUB}", check=False):
        r.fail(f"this stage branch shares history with {HUB}; stage branches must be orphan branches (Rule 2)")
    else:
        r.ok(f"orphan branch (no shared history with {HUB})")


def main() -> int:
    try:
        if not git("rev-parse", "--is-inside-work-tree", check=False):
            print("[ERROR] Run this inside the repository clone")
            return 1
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        print(f"Checking branch '{branch}'")
        git("fetch", "-q", "origin", HUB, check=False)
        r = Report()
        if branch == HUB:
            check_hub(r)
        elif branch.startswith(STAGE_PREFIX):
            check_stage(branch, r)
        else:
            r.warn(f"'{branch}' is neither {HUB} nor a {STAGE_PREFIX}* branch; only common rules are checked "
                   "(see docs/BRANCHING.md, Rule 1)")
        check_common(branch, r)
        print(f"\nResult: {len(r.failures)} failure(s), {len(r.warnings)} warning(s)")
        return 1 if r.failures else 0
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

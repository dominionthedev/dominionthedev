#!/usr/bin/env python3
"""
inject_notes.py

Fetches the most recently committed .md files from DominionDev's notes repo
and injects them as a formatted list between <!-- NOTES:START --> and
<!-- NOTES:END --> markers in README.md.

Usage (called by GitHub Actions):
    python scripts/inject_notes.py

Environment variables:
    GITHUB_TOKEN       — PAT with repo read scope (required)
    NOTES_REPO         — owner/repo of the notes repo   (default: dominionthedev/notes)
    README_PATH        — path to the README to patch     (default: README.md)
    MAX_NOTES          — how many notes to show          (default: 5)
    SKIP_FILES         — comma-separated filenames to ignore
                         (default: README.md,about_me.md,projects.md,task.md)
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
NOTES_REPO   = os.environ.get("NOTES_REPO",   "dominionthedev/notes")
README_PATH  = os.environ.get("README_PATH",  "README.md.tpl")
MAX_NOTES    = int(os.environ.get("MAX_NOTES", "5"))

_skip_raw    = os.environ.get("SKIP_FILES", "README.md,about_me.md,projects.md,task.md")
SKIP_FILES   = {s.strip().lower() for s in _skip_raw.split(",") if s.strip()}

START_MARKER = "<!-- NOTES:START -->"
END_MARKER   = "<!-- NOTES:END -->"

NOTES_REPO_URL = f"https://github.com/{NOTES_REPO}"

# ── GitHub API helpers ────────────────────────────────────────────────────────

def gh_get(path: str) -> dict | list:
    """Make an authenticated GET to the GitHub REST API."""
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept",               "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[inject-notes] GitHub API error {e.code} for {url}: {body}", file=sys.stderr)
        sys.exit(1)


def get_tree(repo: str) -> list[dict]:
    """Return the flat file tree for the default branch."""
    info    = gh_get(f"/repos/{repo}")
    branch  = info["default_branch"]
    tree    = gh_get(f"/repos/{repo}/git/trees/{branch}?recursive=1")
    return tree.get("tree", [])


def get_last_commit_date(repo: str, filepath: str) -> datetime:
    """Return the datetime of the most recent commit that touched `filepath`."""
    commits = gh_get(f"/repos/{repo}/commits?path={filepath}&per_page=1")
    if not commits:
        return datetime.min.replace(tzinfo=timezone.utc)
    raw = commits[0]["commit"]["committer"]["date"]  # e.g. "2025-03-10T14:22:00Z"
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


# ── Core logic ────────────────────────────────────────────────────────────────

def collect_notes(repo: str) -> list[dict]:
    """
    Find all .md files in the repo (excluding skipped ones and dotfiles/dirs),
    fetch their last-commit date, and return the N most recent.
    """
    tree = get_tree(repo)

    candidates = []
    for node in tree:
        if node.get("type") != "blob":
            continue
        path = node["path"]
        filename = path.split("/")[-1]

        # skip hidden files, skip-list, non-markdown
        if filename.startswith("."):
            continue
        if not filename.lower().endswith(".md"):
            continue
        if filename.lower() in SKIP_FILES:
            continue
        # skip files inside hidden dirs (e.g. .obsidian)
        if any(part.startswith(".") for part in path.split("/")[:-1]):
            continue

        candidates.append(path)

    print(f"[inject-notes] Found {len(candidates)} candidate note(s)", file=sys.stderr)

    dated = []
    for path in candidates:
        ts = get_last_commit_date(repo, path)
        name = path.split("/")[-1].replace(".md", "").replace("-", " ").replace("_", " ").title()
        url  = f"{NOTES_REPO_URL}/blob/main/{path}"
        dated.append({"path": path, "name": name, "url": url, "date": ts})

    dated.sort(key=lambda n: n["date"], reverse=True)
    return dated[:MAX_NOTES]


def format_notes(notes: list[dict]) -> str:
    """Render notes as a markdown list with date stamps."""
    if not notes:
        return "_No notes yet._"

    lines = []
    for note in notes:
        date_str = note["date"].strftime("%b %d, %Y")
        lines.append(f"- [`{note['path']}`]({note['url']}) — {date_str}")

    lines.append(f"\n→ [Browse all notes]({NOTES_REPO_URL})")
    return "\n".join(lines)


def inject(readme_path: str, content: str) -> bool:
    """
    Replace the block between START_MARKER and END_MARKER in readme_path
    with `content`. Returns True if the file was changed.
    """
    with open(readme_path, "r", encoding="utf-8") as f:
        original = f.read()

    start_idx = original.find(START_MARKER)
    end_idx   = original.find(END_MARKER)

    if start_idx == -1 or end_idx == -1:
        print(
            f"[inject-notes] Markers not found in {readme_path}. "
            "Make sure both <!-- NOTES:START --> and <!-- NOTES:END --> exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    if end_idx <= start_idx:
        print("[inject-notes] END marker appears before START marker.", file=sys.stderr)
        sys.exit(1)

    before  = original[: start_idx + len(START_MARKER)]
    after   = original[end_idx:]
    updated = f"{before}\n{content}\n{after}"

    if updated == original:
        print("[inject-notes] README unchanged — notes are up to date.", file=sys.stderr)
        return False

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"[inject-notes] Injected {len(content.splitlines())} line(s) into {readme_path}", file=sys.stderr)
    return True


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not GITHUB_TOKEN:
        print("[inject-notes] Warning: GITHUB_TOKEN not set. Unauthenticated rate limits apply.", file=sys.stderr)

    print(f"[inject-notes] Fetching notes from {NOTES_REPO} ...", file=sys.stderr)
    notes   = collect_notes(NOTES_REPO)
    content = format_notes(notes)
    changed = inject(README_PATH, content)

    print(f"[inject-notes] Done. Changed={changed}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()

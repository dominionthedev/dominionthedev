#!/usr/bin/env python3
"""
inject_repos.py

Fetches the most recently created repos from dominionthedev and leraniode
and injects them as a formatted list between <!-- ORG_REPOS:START --> and
<!-- ORG_REPOS:END -->, <!-- PERSONAL_REPOS:START --> and <!-- PERSONAL_REPOS:END --> in the README.md.tpl file.

Usage (called by GitHub Actions):
    python scripts/inject_repos.py

Environment variables:
    GITHUB_TOKEN       — PAT with repo read scope (required)
    NOTES_REPO         — owner/repo of the notes repo   (default: dominionthedev/notes)
    USERNAME           — GitHub username                 (default: dominionthedev)
    ORG_NAME           — GitHub org name                 (default: leraniode)
    README_PATH        — path to the README template     (default: README.md.tpl)
    MAX_ORG            — max number of org repos to show  (default: 6)
    MAX_PERSONAL       — max number of personal repos     (default: 4)
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
USERNAME     = os.getenv("USERNAME", "dominionthedev")
ORG_NAME     = os.getenv("ORG_NAME", "leraniode")
README_PATH  = os.getenv("README_PATH", "README.md.tpl")

MAX_ORG      = int(os.getenv("MAX_ORG", "6"))
MAX_PERSONAL = int(os.getenv("MAX_PERSONAL", "4"))

ORG_START = "<!-- ORG_REPOS:START -->"
ORG_END   = "<!-- ORG_REPOS:END -->"

PER_START = "<!-- PERSONAL_REPOS:START -->"
PER_END   = "<!-- PERSONAL_REPOS:END -->"


def gh_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"[inject-repos] API error {e.code}", file=sys.stderr)
        sys.exit(1)


def fetch_repos(url, limit):
    repos = gh_get(url)
    repos.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    return repos[:limit]


def format_repos(repos):
    lines = []
    for r in repos:
        name = r["name"]
        url  = r["html_url"]
        desc = r["description"] or "No description"
        lines.append(f"- **[{name}]({url})** — {desc}")
    return "\n".join(lines) if lines else "_No repos found._"


def inject_block(content, start, end, new):
    s = content.find(start)
    e = content.find(end)

    if s == -1 or e == -1:
        print("[inject-repos] markers missing", file=sys.stderr)
        sys.exit(1)

    before = content[: s + len(start)]
    after  = content[e:]

    return f"{before}\n{new}\n{after}"


def main():
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    print("[inject-repos] Fetching org repos...", file=sys.stderr)
    org = fetch_repos(f"https://api.github.com/orgs/{ORG_NAME}/repos", MAX_ORG)

    print("[inject-repos] Fetching personal repos...", file=sys.stderr)
    personal = fetch_repos(f"https://api.github.com/users/{USERNAME}/repos", MAX_PERSONAL)

    content = inject_block(content, ORG_START, ORG_END, format_repos(org))
    content = inject_block(content, PER_START, PER_END, format_repos(personal))

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("[inject-repos] Done", file=sys.stderr)


if __name__ == "__main__":
    main()
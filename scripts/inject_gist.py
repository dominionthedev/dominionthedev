#!/usr/bin/env python3
"""
inject_gist.py

Fetches the most recent gists from a GitHub user and injects them
between <!-- GISTS:START --> and <!-- GISTS:END --> markers.

Usage:
    python scripts/inject_gist.py

Environment variables:
    GITHUB_TOKEN — PAT (optional but recommended)
    USERNAME     — GitHub username (default: GITHUB_ACTOR or dominionthedev)
    README_PATH  — path to README template (default: README.md)
    MAX_GISTS    — number of gists to show (default: 3)
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
USERNAME     = os.environ.get("USERNAME") or os.environ.get("GITHUB_ACTOR") or "dominionthedev"
README_PATH  = os.environ.get("README_PATH", "README.md")
MAX_GISTS    = int(os.environ.get("MAX_GISTS", "3"))

START_MARKER = "<!-- GISTS:START -->"
END_MARKER   = "<!-- GISTS:END -->"

# ── GitHub API helper ─────────────────────────────────────────────────────────

def gh_get(url: str) -> list | dict:
    """Make an authenticated GET request."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[inject-gists] GitHub API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


# ── Core logic ────────────────────────────────────────────────────────────────

def fetch_gists(username: str) -> list[dict]:
    """Fetch user gists."""
    url = f"https://api.github.com/users/{username}/gists"
    data = gh_get(url)

    # sort manually (GitHub already sorts, but we control it)
    data.sort(key=lambda g: g.get("created_at", ""), reverse=True)

    return data[:MAX_GISTS]


def format_gists(gists: list[dict]) -> str:
    """Render gists into markdown."""
    if not gists:
        return "_No gists yet._"

    lines = []

    for gist in gists:
        desc = gist.get("description") or "No description"
        url  = gist.get("html_url")

        raw_date = gist.get("created_at")
        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        date_str = dt.strftime("%b %Y")

        lines.append(f"- [{desc}]({url}) — `{date_str}`")

    return "\n".join(lines)


def inject(readme_path: str, content: str) -> bool:
    """Inject content between markers."""
    with open(readme_path, "r", encoding="utf-8") as f:
        original = f.read()

    start_idx = original.find(START_MARKER)
    end_idx   = original.find(END_MARKER)

    if start_idx == -1 or end_idx == -1:
        print(
            "[inject-gists] Markers not found. Ensure <!-- GISTS:START --> and <!-- GISTS:END --> exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    if end_idx <= start_idx:
        print("[inject-gists] END marker appears before START marker.", file=sys.stderr)
        sys.exit(1)

    before  = original[: start_idx + len(START_MARKER)]
    after   = original[end_idx:]
    updated = f"{before}\n{content}\n{after}"

    if updated == original:
        print("[inject-gists] README unchanged — gists up to date.", file=sys.stderr)
        return False

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"[inject-gists] Injected {len(content.splitlines())} line(s)", file=sys.stderr)
    return True


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not GITHUB_TOKEN:
        print("[inject-gists] Warning: No GITHUB_TOKEN — rate limits apply.", file=sys.stderr)

    print(f"[inject-gists] Fetching gists for {USERNAME}...", file=sys.stderr)

    gists   = fetch_gists(USERNAME)
    content = format_gists(gists)
    changed = inject(README_PATH, content)

    print(f"[inject-gists] Done. Changed={changed}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
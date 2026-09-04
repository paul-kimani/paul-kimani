#!/usr/bin/env python3
"""Render GitHub stats and top-language cards as SVG, from the GraphQL API.

No third-party service, no Vercel, no rate-limited shared instance. Standard
library only. Inside a GitHub Action, GITHUB_TOKEN is injected automatically.

Usage
-----
  GITHUB_TOKEN=ghp_xxx python scripts/stats_card.py --user paul-kimani
  python scripts/stats_card.py --demo          # offline render check
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

W, H = 520, 250
BG, LINE, DIM, TEXT, ACCENT = "#0D1117", "#30363D", "#7D8590", "#E6EDF3", "#58A6FF"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-profile-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read())
    if "errors" in payload:
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    return payload["data"]["user"]


def summarize(user: dict):
    repos = user["repositories"]["nodes"]
    contrib = user["contributionsCollection"]
    stats = {
        "Commits": contrib["totalCommitContributions"] + contrib["restrictedContributionsCount"],
        "Stars": sum(r["stargazerCount"] for r in repos),
        "Pull requests": user["pullRequests"]["totalCount"],
        "Repositories": user["repositories"]["totalCount"],
        "Followers": user["followers"]["totalCount"],
    }

    sizes: dict[str, int] = {}
    colours: dict[str, str] = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colours[name] = edge["node"]["color"] or ACCENT
    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    total = sum(v for _, v in ranked) or 1
    langs = [(n, v / total, colours[n]) for n, v in ranked]
    return stats, langs


DEMO = (
    {"Commits": 1284, "Stars": 37, "Pull requests": 62,
     "Repositories": 24, "Followers": 4},
    [("Python", 0.44, "#3572A5"), ("C#", 0.27, "#178600"),
     ("C++", 0.11, "#f34b7d"), ("Julia", 0.08, "#a270ba"),
     ("TypeScript", 0.06, "#3178c6"), ("Shell", 0.04, "#89e051")],
)


def frame(title: str, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{title}">
  <rect width="{W}" height="{H}" rx="10" fill="{BG}" stroke="{LINE}"/>
  <g font-family="{MONO}">
    <text x="24" y="36" fill="{TEXT}" font-size="14" font-weight="700">{title}</text>
    <path d="M24 52H{W - 24}" stroke="{LINE}"/>
{body}
  </g>
</svg>
'''


def stats_svg(stats: dict) -> str:
    rows = []
    y = 82
    for label, value in stats.items():
        rows.append(
            f'    <text x="24" y="{y}" fill="{DIM}" font-size="12">{label}</text>'
            f'<text x="{W - 24}" y="{y}" fill="{TEXT}" font-size="15" font-weight="700" '
            f'text-anchor="end">{value:,}</text>'
            f'<path d="M24 {y + 12}H{W - 24}" stroke="#161B22"/>'
        )
        y += 32
    return frame("GitHub activity", "\n".join(rows))


def langs_svg(langs) -> str:
    parts, x = [], 24.0
    bar_w = W - 48
    for name, share, colour in langs:
        seg = bar_w * share
        parts.append(f'    <rect x="{x:.1f}" y="72" width="{seg:.1f}" height="10" fill="{colour}"/>')
        x += seg

    rows, y = [], 112
    for i, (name, share, colour) in enumerate(langs):
        col = 24 if i % 2 == 0 else W / 2
        if i % 2 == 0 and i:
            y += 26
        rows.append(
            f'    <circle cx="{col + 5}" cy="{y - 4}" r="5" fill="{colour}"/>'
            f'<text x="{col + 18}" y="{y}" fill="{TEXT}" font-size="11.5">{name}</text>'
            f'<text x="{col + 210}" y="{y}" fill="{DIM}" font-size="11.5" '
            f'text-anchor="end">{share * 100:.1f}%</text>'
        )
    return frame("Language distribution", "\n".join(parts + rows))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--user", default="paul-kimani")
    p.add_argument("--demo", action="store_true", help="render from stub data, no API call")
    p.add_argument("--stats-out", default="assets/card-stats.svg")
    p.add_argument("--langs-out", default="assets/card-langs.svg")
    a = p.parse_args()

    if a.demo:
        stats, langs = DEMO
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("set GITHUB_TOKEN (a classic PAT with read:user, or the "
                             "token injected by GitHub Actions)")
        stats, langs = summarize(fetch(a.user, token))

    for path, svg in ((a.stats_out, stats_svg(stats)), (a.langs_out, langs_svg(langs))):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()

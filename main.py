#!/usr/bin/env python3
"""Fetch GitHub activity and visualize contributions, languages, and repo stats."""

import argparse
import json
import sys
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

import requests

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

CHARTS_DIR = Path(__file__).parent / "charts"
API_BASE = "https://api.github.com"


class GitHubStats:
    def __init__(self, username: str, token: str | None = None):
        self.username = username
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"

    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        url = f"{API_BASE}{endpoint}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=15)
        if resp.status_code == 403:
            print("  Rate limited. Use a token with --token for higher limits.")
            sys.exit(1)
        resp.raise_for_status()
        return resp.json()

    def _get_paginated(self, endpoint: str, max_pages: int = 5) -> list:
        items = []
        for page in range(1, max_pages + 1):
            data = self._get(endpoint, params={"per_page": 100, "page": page})
            if not data:
                break
            items.extend(data)
        return items

    def get_profile(self) -> dict:
        return self._get(f"/users/{self.username}")

    def get_repos(self) -> list[dict]:
        return self._get_paginated(f"/users/{self.username}/repos")

    def get_events(self) -> list[dict]:
        return self._get_paginated(f"/users/{self.username}/events", max_pages=3)

    def get_languages(self, repos: list[dict]) -> dict[str, int]:
        lang_counter = Counter()
        for repo in repos:
            if repo.get("language"):
                lang_counter[repo["language"]] += repo.get("size", 0)
        return dict(lang_counter.most_common(15))

    def get_repo_stats(self, repos: list[dict]) -> dict:
        total_stars = sum(r.get("stargazers_count", 0) for r in repos)
        total_forks = sum(r.get("forks_count", 0) for r in repos)
        total_size = sum(r.get("size", 0) for r in repos)
        public = sum(1 for r in repos if not r.get("private"))
        private = sum(1 for r in repos if r.get("private"))

        top_starred = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:5]
        top_forked = sorted(repos, key=lambda r: r.get("forks_count", 0), reverse=True)[:5]
        recently_updated = sorted(repos, key=lambda r: r.get("updated_at", ""), reverse=True)[:5]

        return {
            "total_repos": len(repos),
            "public": public,
            "private": private,
            "total_stars": total_stars,
            "total_forks": total_forks,
            "total_size_mb": round(total_size / 1024, 1),
            "top_starred": top_starred,
            "top_forked": top_forked,
            "recently_updated": recently_updated,
        }

    def get_activity_summary(self, events: list[dict]) -> dict:
        event_types = Counter()
        daily_activity = Counter()
        for event in events:
            event_types[event["type"]] += 1
            day = event["created_at"][:10]
            daily_activity[day] += 1
        return {
            "total_events": len(events),
            "event_types": dict(event_types.most_common()),
            "daily_activity": dict(sorted(daily_activity.items())),
        }


def print_profile(profile: dict):
    print(f"\n{'=' * 55}")
    print(f"  GitHub Profile: {profile.get('login', 'N/A')}")
    print(f"{'=' * 55}")
    print(f"  Name:      {profile.get('name', 'N/A')}")
    print(f"  Bio:       {profile.get('bio', 'N/A')}")
    print(f"  Location:  {profile.get('location', 'N/A')}")
    print(f"  Company:   {profile.get('company', 'N/A')}")
    print(f"  Followers: {profile.get('followers', 0)}")
    print(f"  Following: {profile.get('following', 0)}")
    print(f"  Public repos: {profile.get('public_repos', 0)}")
    print(f"  Created:   {profile.get('created_at', 'N/A')[:10]}")


def print_repo_stats(stats: dict):
    print(f"\n--- Repository Stats ---")
    print(f"  Total:  {stats['total_repos']} ({stats['public']} public, {stats['private']} private)")
    print(f"  Stars:  {stats['total_stars']}")
    print(f"  Forks:  {stats['total_forks']}")
    print(f"  Size:   {stats['total_size_mb']} MB")

    print(f"\n  Top Starred:")
    for r in stats["top_starred"]:
        print(f"    ⭐ {r['stargazers_count']:>3} | {r['name']}")

    print(f"\n  Recently Updated:")
    for r in stats["recently_updated"]:
        updated = r.get("updated_at", "")[:10]
        print(f"    {updated} | {r['name']}")


def print_languages(languages: dict):
    if not languages:
        return
    print(f"\n--- Languages ---")
    total = sum(languages.values())
    for lang, size in languages.items():
        pct = size / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {lang:<15} {pct:>5.1f}% {bar}")


def print_activity(activity: dict):
    print(f"\n--- Recent Activity ({activity['total_events']} events) ---")
    event_labels = {
        "PushEvent": "Pushes",
        "CreateEvent": "Creates",
        "PullRequestEvent": "PRs",
        "IssuesEvent": "Issues",
        "WatchEvent": "Stars",
        "ForkEvent": "Forks",
        "IssueCommentEvent": "Comments",
    }
    for event_type, count in activity["event_types"].items():
        label = event_labels.get(event_type, event_type)
        print(f"  {label:<20} {count}")


def generate_charts(languages: dict, stats: dict, activity: dict):
    if not HAS_MATPLOTLIB:
        print("  matplotlib required for charts. Install: pip install matplotlib")
        return

    CHARTS_DIR.mkdir(exist_ok=True)

    if languages:
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = plt.cm.Set3(range(len(languages)))
        wedges, texts, autotexts = ax.pie(
            languages.values(), labels=languages.keys(),
            autopct="%1.1f%%", colors=colors, startangle=90
        )
        ax.set_title(f"Language Distribution", fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / "languages.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved: charts/languages.png")

    top = stats.get("top_starred", [])
    if top:
        fig, ax = plt.subplots(figsize=(10, 5))
        names = [r["name"][:20] for r in top]
        stars = [r["stargazers_count"] for r in top]
        bars = ax.barh(names, stars, color="#f1c40f")
        ax.set_xlabel("Stars")
        ax.set_title("Top Repositories by Stars", fontsize=14, fontweight="bold")
        ax.invert_yaxis()
        for bar, val in zip(bars, stars):
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2, str(val), va="center")
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / "top_repos.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved: charts/top_repos.png")

    daily = activity.get("daily_activity", {})
    if daily:
        fig, ax = plt.subplots(figsize=(12, 4))
        dates = list(daily.keys())
        counts = list(daily.values())
        ax.bar(range(len(dates)), counts, color="#3498db")
        ax.set_ylabel("Events")
        ax.set_title("Daily Activity", fontsize=14, fontweight="bold")
        step = max(1, len(dates) // 8)
        ax.set_xticks(range(0, len(dates), step))
        ax.set_xticklabels([dates[i] for i in range(0, len(dates), step)], rotation=45)
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / "daily_activity.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved: charts/daily_activity.png")


def main():
    parser = argparse.ArgumentParser(description="GitHub Stats Dashboard")
    parser.add_argument("username", help="GitHub username")
    parser.add_argument("--token", "-t", help="GitHub personal access token (for higher rate limits)")
    parser.add_argument("--charts", "-c", action="store_true", help="Generate chart images")
    parser.add_argument("--export-json", help="Export stats to JSON file")
    args = parser.parse_args()

    gh = GitHubStats(args.username, args.token)

    print(f"  Fetching data for {args.username}...")
    profile = gh.get_profile()
    repos = gh.get_repos()
    events = gh.get_events()

    languages = gh.get_languages(repos)
    stats = gh.get_repo_stats(repos)
    activity = gh.get_activity_summary(events)

    print_profile(profile)
    print_repo_stats(stats)
    print_languages(languages)
    print_activity(activity)

    if args.charts:
        print(f"\n--- Generating Charts ---")
        generate_charts(languages, stats, activity)

    if args.export_json:
        report = {
            "profile": {k: profile.get(k) for k in ["login", "name", "bio", "followers", "following", "public_repos"]},
            "stats": {k: v for k, v in stats.items() if k not in ["top_starred", "top_forked", "recently_updated"]},
            "languages": languages,
            "activity": activity,
        }
        with open(args.export_json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n  Exported to {args.export_json}")

    print("\nDone!")


if __name__ == "__main__":
    main()

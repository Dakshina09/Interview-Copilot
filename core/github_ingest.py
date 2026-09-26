"""
Pull a user's public GitHub repos (metadata + README) as resume source material.

Unauthenticated GitHub API allows 60 requests/hour: 1 for the repo list + 1 README per
repo. Set GITHUB_TOKEN (env or Streamlit secrets) to raise that to 5,000/hour.
"""

from __future__ import annotations
import base64
import os
import re
from dataclasses import dataclass, field

import httpx

API = "https://api.github.com"
MAX_REPOS = 25
README_CHARS = 4000


@dataclass
class Repo:
    name: str
    url: str
    description: str = ""
    language: str = ""
    topics: list[str] = field(default_factory=list)
    stars: int = 0
    updated_at: str = ""
    homepage: str = ""
    readme: str = ""

    def source_text(self) -> str:
        """Everything we're allowed to make claims from for this project."""
        parts = [self.name.replace("-", " ").replace("_", " "), self.description,
                 f"Language: {self.language}" if self.language else "",
                 f"Topics: {', '.join(self.topics)}" if self.topics else "", self.readme]
        return "\n".join(p for p in parts if p)


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def clean_readme(md: str) -> str:
    """Strip markup that wastes LLM context: badges, images, HTML, code blocks, links."""
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    md = re.sub(r"<[^>]+>", " ", md)
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)              # images/badges
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)             # links -> text
    md = re.sub(r"^\s*[-*_]{3,}\s*$", " ", md, flags=re.M)       # rules
    md = re.sub(r"[ \t]+", " ", md)
    md = re.sub(r"\n\s*\n+", "\n", md)
    return md.strip()[:README_CHARS]


def parse_username(text: str) -> str:
    """Accept 'user', '@user' or any github.com/user URL."""
    text = text.strip().rstrip("/")
    m = re.search(r"github\.com/([A-Za-z0-9-]+)", text)
    return m.group(1) if m else text.lstrip("@")


def find_github_in_text(text: str) -> str:
    m = re.search(r"github\.com/([A-Za-z0-9-]+)", text or "")
    return m.group(1) if m else ""


class GitHubError(RuntimeError):
    pass


def fetch_repos(username: str, include_forks: bool = False) -> list[Repo]:
    username = parse_username(username)
    with httpx.Client(headers=_headers(), timeout=20) as client:
        r = client.get(f"{API}/users/{username}/repos",
                       params={"per_page": 100, "sort": "updated", "type": "owner"})
        if r.status_code == 404:
            raise GitHubError(f"GitHub user '{username}' not found.")
        if r.status_code == 403:
            raise GitHubError("GitHub rate limit hit. Wait an hour or set GITHUB_TOKEN.")
        r.raise_for_status()

        repos = []
        for d in r.json():
            if d.get("fork") and not include_forks:
                continue
            if d.get("archived"):
                continue
            repos.append(Repo(
                name=d["name"], url=d["html_url"], description=d.get("description") or "",
                language=d.get("language") or "", topics=d.get("topics") or [],
                stars=d.get("stargazers_count", 0), updated_at=d.get("updated_at", ""),
                homepage=d.get("homepage") or "",
            ))
        repos = repos[:MAX_REPOS]

        for repo in repos:
            rr = client.get(f"{API}/repos/{username}/{repo.name}/readme")
            if rr.status_code == 200:
                try:
                    raw = base64.b64decode(rr.json().get("content", "")).decode("utf-8", "ignore")
                    repo.readme = clean_readme(raw)
                except Exception:
                    pass
            elif rr.status_code == 403:
                break    # rate limited -- keep what we have
    return repos

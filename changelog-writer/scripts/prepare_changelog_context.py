#!/usr/bin/env python3
"""Collect current version and change context for changelog drafting."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

VERSION_HEADING_RE = re.compile(
    r"^##\s+v?(?P<version>\d+\.\d+\.\d+)(?:\s*-\s*(?P<release_date>\d{4}-\d{2}-\d{2}))?\s*$",
    re.IGNORECASE,
)

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass
class ReleaseEntry:
    version: str
    release_date: str | None
    line_number: int


def run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def run_command(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode, output


def find_changelog(repo: Path, explicit_path: str | None) -> Path | None:
    if explicit_path:
        candidate = (repo / explicit_path).resolve()
        return candidate if candidate.exists() else None

    for candidate in [repo / "CHANGELOG.md", repo / "docs" / "CHANGELOG.md"]:
        if candidate.exists():
            return candidate

    return None


def parse_changelog_versions(changelog: Path) -> list[ReleaseEntry]:
    entries: list[ReleaseEntry] = []
    for idx, raw_line in enumerate(changelog.read_text(encoding="utf-8").splitlines(), start=1):
        match = VERSION_HEADING_RE.match(raw_line.strip())
        if not match:
            continue
        entries.append(
            ReleaseEntry(
                version=match.group("version"),
                release_date=match.group("release_date"),
                line_number=idx,
            )
        )
    return entries


def bump_patch(version: str | None) -> str | None:
    if not version:
        return None

    match = SEMVER_RE.match(version)
    if not match:
        return None

    major, minor, patch = (int(item) for item in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def read_frontend_version(repo: Path) -> str | None:
    package_json = repo / "frontend" / "package.json"
    if not package_json.exists():
        return None

    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    version = payload.get("version")
    return str(version) if isinstance(version, str) and version.strip() else None


def read_backend_version(repo: Path) -> str | None:
    pyproject = repo / "backend" / "pyproject.toml"
    if not pyproject.exists():
        return None

    version_re = re.compile(r'^version\s*=\s*"(?P<version>[^"]+)"$')
    in_project_section = False
    for raw_line in pyproject.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("["):
            in_project_section = line == "[project]"
            continue

        if not in_project_section:
            continue

        match = version_re.match(line)
        if match:
            return match.group("version")

    return None


def resolve_repo_slug(repo: Path) -> str | None:
    remote_url = run_git(repo, ["remote", "get-url", "origin"])
    if not remote_url:
        return None

    normalized_url = remote_url.strip()
    for prefix in ("git@github.com:", "https://github.com/", "ssh://git@github.com/"):
        if normalized_url.startswith(prefix):
            normalized_url = normalized_url[len(prefix) :]
            break
    else:
        return None

    if normalized_url.endswith(".git"):
        normalized_url = normalized_url[:-4]

    normalized_url = normalized_url.strip("/")
    if normalized_url.count("/") != 1:
        return None

    return normalized_url


def version_to_tag(version: str | None) -> str | None:
    if not version:
        return None
    return f"v{version}"


def build_github_release_url(repo_slug: str | None, tag_name: str | None) -> str | None:
    if not repo_slug or not tag_name:
        return None
    return f"https://github.com/{repo_slug}/releases/tag/{tag_name}"


def detect_gh_cli_status() -> dict[str, str | bool]:
    exit_code, version_output = run_command(["gh", "--version"])
    if exit_code != 0:
        return {
            "installed": False,
            "authenticated": False,
            "version": "",
            "auth_status": "gh not installed",
        }

    auth_exit_code, auth_output = run_command(["gh", "auth", "status", "-h", "github.com"])
    safe_auth_lines = []
    for line in auth_output.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("- token:"):
            safe_auth_lines.append("  - Token: [masked]")
            continue
        safe_auth_lines.append(line)

    return {
        "installed": True,
        "authenticated": auth_exit_code == 0,
        "version": version_output.splitlines()[0] if version_output else "",
        "auth_status": "\n".join(safe_auth_lines),
    }


def classify_commit(subject: str) -> str:
    lowered = subject.lower()
    if lowered.startswith("feat:"):
        return "added"
    if lowered.startswith("fix:"):
        return "fixed"
    if lowered.startswith("refactor:") or lowered.startswith("perf:"):
        return "changed"
    if lowered.startswith("docs:") or lowered.startswith("chore:") or lowered.startswith("test:"):
        return "maintenance"
    return "other"


def collect_commits_since_changelog(repo: Path, changelog: Path | None) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "added": [],
        "changed": [],
        "fixed": [],
        "maintenance": [],
        "other": [],
    }

    commit_range = "HEAD"
    if changelog is not None:
        relative_path = changelog.relative_to(repo)
        marker = run_git(repo, ["log", "-1", "--format=%H", "--", str(relative_path)])
        if marker:
            commit_range = f"{marker}..HEAD"

    raw_commits = run_git(repo, ["log", "--pretty=format:%h\t%s", commit_range])
    if not raw_commits:
        return buckets

    for line in raw_commits.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", maxsplit=1)
        if len(parts) != 2:
            continue
        sha, subject = parts
        bucket = classify_commit(subject)
        buckets[bucket].append(f"{subject} ({sha})")

    return buckets


def render_markdown_draft(version: str | None, commits: dict[str, list[str]]) -> str:
    heading_version = version or "x.y.z"
    today = date.today().isoformat()
    lines = [f"## v{heading_version} - {today}", ""]

    mapping = [
        ("added", "Added"),
        ("changed", "Changed"),
        ("fixed", "Fixed"),
        ("maintenance", "Maintenance"),
        ("other", "Other"),
    ]

    has_content = False
    for key, label in mapping:
        items = commits.get(key, [])
        if not items:
            continue
        has_content = True
        lines.append(f"- {label}:")
        for item in items:
            lines.append(f"\t- {item}")
        lines.append("")

    if not has_content:
        lines.append("- Maintenance:")
        lines.append("\t- Internal changes only.")
        lines.append("")

    return "\n".join(lines).rstrip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare changelog context from repository state.")
    parser.add_argument("--repo", default=".", help="Repository root path.")
    parser.add_argument("--changelog", default=None, help="Optional changelog path relative to repo.")
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format.",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    changelog_path = find_changelog(repo, args.changelog)
    versions = parse_changelog_versions(changelog_path) if changelog_path else []
    current_version = versions[0].version if versions else None
    suggested_version = bump_patch(current_version)
    suggested_tag = version_to_tag(suggested_version)
    repo_slug = resolve_repo_slug(repo)
    gh_release_url = build_github_release_url(repo_slug, suggested_tag)
    commits = collect_commits_since_changelog(repo, changelog_path)
    draft_markdown = render_markdown_draft(suggested_version, commits)
    gh_status = detect_gh_cli_status()

    payload = {
        "repo": str(repo),
        "changelog_path": str(changelog_path) if changelog_path else None,
        "repo_slug": repo_slug,
        "current_version": current_version,
        "suggested_next_version": suggested_version,
        "suggested_tag": suggested_tag,
        "suggested_github_release_url": gh_release_url,
        "frontend_version": read_frontend_version(repo),
        "backend_version": read_backend_version(repo),
        "gh_cli_status": gh_status,
        "release_entries": [
            {
                "version": entry.version,
                "release_date": entry.release_date,
                "line_number": entry.line_number,
            }
            for entry in versions
        ],
        "commits_since_last_changelog": commits,
        "draft_markdown": draft_markdown,
    }

    if args.format == "markdown":
        print(draft_markdown)
        return

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

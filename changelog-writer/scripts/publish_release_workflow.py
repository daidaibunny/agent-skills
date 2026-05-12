#!/usr/bin/env python3
"""Publish a synchronized changelog + git tag + GitHub release workflow."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_HEADING_RE = re.compile(
    r"^##\s+v?(?P<version>\d+\.\d+\.\d+)(?:\s*-\s*\d{4}-\d{2}-\d{2})?\s*$",
    re.IGNORECASE,
)


def run_command(command: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def run_checked(command: list[str], *, cwd: Path | None = None) -> str:
    exit_code, stdout, stderr = run_command(command, cwd=cwd)
    if exit_code != 0:
        output = stderr or stdout or "unknown error"
        raise RuntimeError(f"Command failed ({' '.join(command)}): {output}")
    return stdout


def find_changelog(repo: Path, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = (repo / explicit_path).resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"changelog not found: {candidate}")

    for candidate in (repo / "CHANGELOG.md", repo / "docs" / "CHANGELOG.md"):
        if candidate.exists():
            return candidate

    raise FileNotFoundError("CHANGELOG.md not found in repo root or docs/")


def resolve_repo_slug(repo: Path, remote: str) -> str:
    remote_url = run_checked(["git", "-C", str(repo), "remote", "get-url", remote])
    normalized = remote_url.strip()
    for prefix in ("git@github.com:", "https://github.com/", "ssh://git@github.com/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break

    if normalized.endswith(".git"):
        normalized = normalized[:-4]

    normalized = normalized.strip("/")
    if normalized.count("/") != 1:
        raise RuntimeError(f"unsupported GitHub remote URL format: {remote_url}")

    return normalized


def resolve_tag(version: str, tag_prefix: str) -> str:
    if not SEMVER_RE.match(version):
        raise ValueError("version must be semantic version (x.y.z)")
    return f"{tag_prefix}{version}"


def build_release_url(repo_slug: str, tag_name: str) -> str:
    return f"https://github.com/{repo_slug}/releases/tag/{tag_name}"


def validate_worktree(repo: Path) -> None:
    status_output = run_checked(["git", "-C", str(repo), "status", "--porcelain"])
    tracked_changes = [
        line for line in status_output.splitlines() if line and not line.startswith("?? ")
    ]
    if tracked_changes:
        raise RuntimeError(
            "tracked changes detected; commit or stash first before publishing release"
        )


def ensure_tag_absent(repo: Path, tag_name: str) -> None:
    existing = run_checked(["git", "-C", str(repo), "tag", "--list", tag_name])
    if any(line.strip() == tag_name for line in existing.splitlines()):
        raise RuntimeError(f"git tag already exists: {tag_name}")


def normalize_notes(note_text: str) -> list[str]:
    normalized_text = note_text.replace("\\n", "\n")
    lines = [line.rstrip() for line in normalized_text.splitlines()]
    normalized: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            normalized.append(stripped)
        elif stripped.startswith("* "):
            normalized.append(f"- {stripped[2:].strip()}")
        else:
            normalized.append(f"- {stripped}")

    if not normalized:
        raise ValueError("release notes content cannot be empty")

    return normalized


def build_changelog_entry(
    *,
    version: str,
    title: str,
    notes: list[str],
    release_url: str,
) -> str:
    today = date.today().isoformat()
    lines = [f"## v{version} - {today}", "", f"- {title.strip()}", *notes, f"- GitHub Release: {release_url}", ""]
    return "\n".join(lines)


def inject_entry(changelog_text: str, version: str, entry: str) -> str:
    lines = changelog_text.splitlines()
    for line in lines:
        match = VERSION_HEADING_RE.match(line.strip())
        if match and match.group("version") == version:
            raise RuntimeError(f"version already exists in changelog: {version}")

    first_release_index: int | None = None
    for index, line in enumerate(lines):
        if line.strip().startswith("## "):
            first_release_index = index
            break

    entry_lines = entry.rstrip("\n").splitlines()

    if first_release_index is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(entry_lines)
        lines.append("")
        return "\n".join(lines) + "\n"

    before = lines[:first_release_index]
    after = lines[first_release_index:]

    if before and before[-1].strip():
        before.append("")

    new_lines = before + entry_lines + [""] + after
    return "\n".join(new_lines).rstrip() + "\n"


def build_github_release_body(title: str, notes: list[str], release_url: str) -> str:
    body_lines = [f"## {title.strip()}", "", *notes, "", f"[Changelog]({release_url})"]
    return "\n".join(body_lines).rstrip() + "\n"


def ensure_gh_ready() -> None:
    gh_version_code, _, _ = run_command(["gh", "--version"])
    if gh_version_code != 0:
        raise RuntimeError("GitHub CLI (gh) is required but not installed")

    auth_code, _, auth_stderr = run_command(["gh", "auth", "status", "-h", "github.com"])
    if auth_code != 0:
        message = auth_stderr or "gh auth status failed"
        raise RuntimeError(f"GitHub CLI not authenticated: {message}")


def resolve_branch(repo: Path, branch: str | None) -> str:
    if branch:
        return branch
    current_branch = run_checked(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"])
    return current_branch.strip() or "main"


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish changelog + tag + GitHub release")
    parser.add_argument("--repo", default=".", help="Repository root path")
    parser.add_argument("--version", required=True, help="Semantic version, e.g. 0.7.0")
    parser.add_argument("--title", required=True, help="Release title")
    parser.add_argument("--notes", required=True, help="User-facing release notes text")
    parser.add_argument("--changelog", default=None, help="Optional changelog path relative to repo")
    parser.add_argument("--remote", default="origin", help="Git remote name")
    parser.add_argument("--branch", default=None, help="Target branch (default: current branch)")
    parser.add_argument("--tag-prefix", default="v", help="Tag prefix (default: v)")
    parser.add_argument("--execute", action="store_true", help="Apply and publish changes")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    changelog_path = find_changelog(repo, args.changelog)
    repo_slug = resolve_repo_slug(repo, args.remote)
    version = args.version.strip()
    tag_name = resolve_tag(version, args.tag_prefix)
    release_url = build_release_url(repo_slug, tag_name)
    branch = resolve_branch(repo, args.branch)

    notes = normalize_notes(args.notes)
    changelog_entry = build_changelog_entry(
        version=version,
        title=args.title,
        notes=notes,
        release_url=release_url,
    )

    current_changelog = changelog_path.read_text(encoding="utf-8")
    updated_changelog = inject_entry(current_changelog, version, changelog_entry)
    github_release_body = build_github_release_body(args.title, notes, release_url)

    if not args.execute:
        print(
            json.dumps(
                {
                    "repo": str(repo),
                    "changelog_path": str(changelog_path),
                    "repo_slug": repo_slug,
                    "branch": branch,
                    "version": version,
                    "tag": tag_name,
                    "github_release_url": release_url,
                    "changelog_preview": changelog_entry,
                    "github_release_body_preview": github_release_body,
                    "execute": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    validate_worktree(repo)
    ensure_tag_absent(repo, tag_name)
    ensure_gh_ready()

    changelog_path.write_text(updated_changelog, encoding="utf-8")

    run_checked(["git", "-C", str(repo), "add", str(changelog_path)])
    run_checked(
        [
            "git",
            "-C",
            str(repo),
            "commit",
            "-m",
            f"docs(changelog): release {tag_name}",
        ]
    )
    commit_sha = run_checked(["git", "-C", str(repo), "rev-parse", "HEAD"])
    run_checked(["git", "-C", str(repo), "tag", "-a", tag_name, "-m", f"Release {tag_name}"])
    run_checked(["git", "-C", str(repo), "push", args.remote, branch])
    run_checked(["git", "-C", str(repo), "push", args.remote, tag_name])

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as handle:
            handle.write(github_release_body)
            tmp_path = handle.name

        run_checked(
            [
                "gh",
                "release",
                "create",
                tag_name,
                "--title",
                f"{tag_name} - {args.title.strip()}",
                "--notes-file",
                tmp_path,
            ],
            cwd=repo,
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    released_url = run_checked(
        ["gh", "release", "view", tag_name, "--json", "url", "-q", ".url"],
        cwd=repo,
    )

    print(
        json.dumps(
            {
                "repo": str(repo),
                "branch": branch,
                "version": version,
                "tag": tag_name,
                "commit": commit_sha,
                "github_release_url": released_url or release_url,
                "execute": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

---
name: asset-tracker-changelog-push-sop
description: Use when the user wants to push the latest finance--tracker changelog into the production in-app release-note stream after a deploy. This skill verifies GitHub release state, compares the previous stable release with the new one, drafts a short user-facing summary, runs the publish script, and confirms the server now shows the same version.
---

# Asset Tracker Changelog Push SOP

## Overview

Use this skill after a successful production deploy when the user wants the new version to appear
inside the app's release-note inbox stream as a short user-facing update, not as a raw technical
changelog dump.

If the user wants GitHub release creation, server deploy, and in-app release-note push in one run,
use `$asset-tracker-release-deploy-sop` instead.

For local defaults, prefer `.env.release-deploy.local`. The publish helper also accepts the legacy
`.env.codex-feedback-automation.local` values for origin and admin login.

## Default Assumptions

- Local repo path is `/Users/lyw/Desktop/finance`.
- The server is already updated and healthy.
- Production SSH should use the saved alias `asset-tracker-aws` when the remote host needs to be
  checked or updated before the push.
- The changelog to publish is the latest `CHANGELOG.md` version unless the user specifies another one.
- The target release already exists on GitHub as `vX.Y.Z`.
- `CHANGELOG.md`, GitHub Release metadata, and the in-app release-note title/content should remain in
  English by default. Only localize them if the user explicitly asks for non-English release copy.

If the server origin, admin username, or target version is unknown, ask one short question.
If the remote deploy state is uncertain, do not push the changelog yet. Verify the host over
`asset-tracker-aws` first, or run `$asset-tracker-server-update-sop` before continuing.

## Workflow

### 1. Local Preflight

Before publishing, verify the local release state:

```bash
cd /Users/lyw/Desktop/finance
git status --short --branch
gh release view vX.Y.Z --json tagName,url,name,isDraft,isPrerelease
```

Do not continue if:

- `CHANGELOG.md` still has local unstaged or staged edits.
- The GitHub release is missing.
- The GitHub release is still a draft or prerelease.

### 2. Compare With The Previous Stable Release

Before drafting the in-app note, inspect what changed since the previous stable release:

```bash
cd /Users/lyw/Desktop/finance
gh release list --limit 10 --json tagName,name,isDraft,isPrerelease,publishedAt
git log --oneline <previous-tag>..vX.Y.Z
git diff --name-only <previous-tag>..vX.Y.Z
```

Draft only 2 to 4 bullets for users, and write them in English. Prioritize:

- visible feature improvements
- reliability or stability gains
- smoother workflows
- fixes that users are likely to notice

Avoid internal-only details unless users directly benefit from them. Usually skip words like:

- Postgres
- Redis
- Alembic
- Docker
- schema migration
- refactor
- dependency bump

Prefer user-facing phrasing such as:

- improved stability
- more reliable sync and updates
- more reliable background work
- smoother page interactions
- more reliable login and data loading

Keep the title and bullets concise and product-facing. Avoid mixed-language release copy.

### 3. Confirm Remote Update State

Before publishing, confirm that the production host is already on the intended code and healthy.
Use the saved SSH alias, not a raw host, unless the user explicitly overrides it:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && git status --short --branch && git rev-parse HEAD && docker compose -f docker-compose.yml -f docker-compose.production.yml ps && curl -k -fsS https://127.0.0.1/api/health && echo'
```

If the remote repo is behind, or the health check fails, stop the changelog push flow and update
the server first.

### 4. Publish To The Server

Run the local helper script:

```bash
cd /Users/lyw/Desktop/finance
python3 scripts/push_release_note_from_changelog.py \
  --env-file .env.release-deploy.local \
  --title 'User-facing title' \
  --content $'- First core change\n- Second core change'
```

The script:

- reads the target version from `CHANGELOG.md`
- verifies the matching GitHub release tag
- logs into the server as admin
- calls `POST /api/admin/release-notes/publish-changelog`
- behaves idempotently for the same version and content
- lets you override the in-app title and content with a shorter user-facing summary

### 5. Verify The Push

Confirm the server accepted the release note:

```bash
curl -fsS https://your-server-origin/api/health && echo
```

If you need a second proof path, log in as admin and verify `/api/admin/release-notes` now contains
the target version.

## Guardrails

- The in-app pushed version must match the GitHub release tag exactly.
- Do not invent a version or push an unpublished changelog.
- Do not push the changelog before confirming the remote host can update correctly and the target
  deploy is healthy.
- Do not paste the full technical changelog into the app inbox unless the user explicitly asks for it.
- If the push endpoint returns a conflict, surface the exact version/content mismatch instead of retrying blindly.
- If the same version was already pushed with the same content, treat that as success.

## Output Contract

When using this skill, respond with:

- The version being pushed.
- The exact publish command.
- A short success or failure verdict.
- The GitHub release URL or the blocker that prevented publication.

---
name: "asset-tracker-release-deploy-sop"
description: "Use when the user wants to publish a finance--tracker version end to end in one run: verify the changelog version, create or verify the GitHub release, deploy main to the server, run health checks, and push a short in-app release note with user-facing bullets."
---

# Asset Tracker Release Deploy SOP

## Overview

Use this skill when the user wants the whole versioned release handled in one flow.

## Default Assumptions

- Local repo path is `/Users/lyw/Desktop/finance`.
- The target branch is `main`.
- The server repo path is `~/finance--tracker`.
- The latest `CHANGELOG.md` entry is the version being released.
- `CHANGELOG.md`, GitHub Release titles and notes, and the in-app release update should be written in
  English by default. Do not switch to Chinese unless the user explicitly asks for localized release copy.
- The release helper script may load defaults from `.env.release-deploy.local` or the legacy
  `.env.codex-feedback-automation.local` when present.
- Production SSH should use the saved alias `asset-tracker-aws` via
  `ASSET_TRACKER_SERVER_SSH`, not a raw host string, unless the user explicitly overrides it.

If the server SSH target, server origin, or admin credentials are unknown, ask one short question.

## Workflow

### 1. Draft User-Facing Bullets

Compare the previous stable release to the new release candidate and compress the result into 2 to 4
user-facing bullets in English.

Prioritize:

- visible feature improvements
- reliability or stability gains
- smoother workflows
- fixes users are likely to notice

Avoid raw internal details such as Postgres, Redis, Alembic, Docker, schema migrations, refactors,
or dependency bumps unless the user explicitly wants technical detail.

The in-app release title should also stay in English and should read like an official product update,
not an internal engineering note.

### 2. Run The One-Command Release Flow

From `/Users/lyw/Desktop/finance`, run:

```bash
cp .env.release-deploy.example .env.release-deploy.local
# fill the real values first
# ASSET_TRACKER_SERVER_SSH should normally stay set to asset-tracker-aws
python3 scripts/release_deploy_and_broadcast.py \
  --env-file .env.release-deploy.local \
  --user-title 'Stability and Experience Updates' \
  --bullet 'First user-facing improvement' \
  --bullet 'Second user-facing improvement'
```

Add a third or fourth `--bullet` when needed, but keep the message short.

`ASSET_TRACKER_SERVER_SSH` should normally be the saved alias `asset-tracker-aws`, which resolves
  to the current production host. Prefer non-interactive SSH keys. If the host only supports password
login, set `ASSET_TRACKER_SERVER_SSH_PASSWORD` in `.env.release-deploy.local`. Only fall back to a
raw host such as `root@<public-ip>` when the alias is intentionally unavailable.

Before the in-app changelog push happens, the remote update must already be proven healthy through
the SSH deploy step. Do not publish the changelog first and then try to fix the server afterwards.

### 3. Success Criteria

The workflow is only complete if all of these succeed:

- GitHub release exists for the same `CHANGELOG.md` version
- `main` is pushed
- the server deploy passes health checks
- the in-app release note is published for the same version

## Output Contract

When using this skill, respond with:

- the version being released
- the exact one-command invocation
- a short success or failure verdict
- the GitHub release URL

---
name: asset-tracker-server-update-sop
description: Use when the user wants to update, redeploy, or verify the finance--tracker server. This skill standardizes preflight checks, risk classification, backup decisions, docker compose deployment, and post-deploy verification for the production nginx + backend + worker + Postgres + Redis stack.
---

# Asset Tracker Server Update SOP

## Overview

Use this skill for routine server updates and redeploys. The goal is to keep every deploy on the same minimal path: inspect risk, back up when the change is dangerous, update with the correct compose files, prove the stack is healthy, and finish versioned releases with a matching in-app changelog push.

If the user wants the full versioned release handled in one command, use
`$asset-tracker-release-deploy-sop` instead.

For local release defaults, prefer `.env.release-deploy.local`. The helper scripts also accept the
legacy `.env.codex-feedback-automation.local` values for origin and admin login.

## Default Assumptions

- Local repo path is `/Users/lyw/Desktop/finance`.
- Server repo path is `~/finance--tracker` unless the user says otherwise.
- Production SSH should use the saved alias `asset-tracker-aws` unless the user explicitly overrides it.
- The target branch is `main`.
- Versioned release artifacts stay in English by default, including `CHANGELOG.md`, GitHub Release
  metadata, and the in-app release-note title/content.
- Production deploys use:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build --remove-orphans
```

- Production Docker access is expected to work from the saved SSH user without `sudo`; the
  `ubuntu` user belongs to the `docker` group on the current host.
- Production health is exposed through nginx on HTTPS. Use `curl -k -fsS
  https://127.0.0.1/api/health`, not the retired direct `:8080` check.
- `backend` owns startup migrations. `worker` waits for a healthy `backend` instead of running Alembic itself.
- User-facing production releases should already have a GitHub release and matching `CHANGELOG.md`
  entry before deployment.

If the user has a different server path, branch, compose override, or network arrangement, ask one short question before running commands.

## Workflow

### 1. Local Source Check

Before touching the server, verify the local repo is in a sane state:

```bash
cd /Users/lyw/Desktop/finance
git status --short --branch
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git log --oneline --decorate -n 5
```

If `HEAD` is not the intended deploy commit, or local changes are still unpushed, stop and tell the user exactly what is outstanding.

If this deploy is meant to notify users, also verify that the target version is already released on
GitHub. If not, stop and run `$changelog-writer` first.

### 2. Server Preflight

On the server, inspect what is about to change before pulling:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && git status --short --branch && git fetch origin && git diff --name-only HEAD..origin/main'
```

Treat the update as higher risk if the diff touches any of these:

- `backend/alembic/versions/`
- `backend/app/models.py`
- `backend/app/database.py`
- `backend/app/settings.py`
- `backend/pyproject.toml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`
- `docker-compose.production.yml`
- `docker-compose.yml`

Also validate the server environment before deployment:

```bash
cd ~/finance--tracker
grep -E "^(ASSET_TRACKER_PUBLIC_ORIGIN|ASSET_TRACKER_SESSION_SECRET|ASSET_TRACKER_API_TOKEN|ASSET_TRACKER_POSTGRES_PASSWORD)=" .env
docker compose -f docker-compose.yml -f docker-compose.production.yml config -q
```

If `.env` is missing required keys, or `docker compose config -q` fails, fix that first.

### 3. Backup Rule

If the update is high risk, or the user explicitly wants a safety snapshot, take a backup before pulling:

```bash
cd ~/finance--tracker
ts="$(date +%Y%m%d-%H%M%S)"
cp .env ".env.bak.${ts}"
mkdir -p backups
docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T postgres \
  sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "backups/postgres-${ts}.sql"
```

For low-risk frontend-only or docs-only changes, you can skip the Postgres dump unless the user asks for a fresh backup anyway.

### 4. Standard Deploy

Run the steady-state deploy with the production compose files:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && git checkout main && git pull --ff-only origin main && docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build --remove-orphans'
```

Do not invent alternate compose files unless the user explicitly changed the server topology.

### 5. Required Verification

Always collect proof before saying the update succeeded:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && docker compose -f docker-compose.yml -f docker-compose.production.yml ps && curl -k -fsS https://127.0.0.1/api/health && echo && docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T redis redis-cli ping && docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T postgres sh -lc '\''psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select * from alembic_version;"'\'' && docker compose -f docker-compose.yml -f docker-compose.production.yml logs --tail=120 backend worker nginx'
```

Success means all of the following are true:

- `backend`, `worker`, `frontend`, `nginx`, `postgres`, and `redis` are up.
- `/api/health` returns `200`.
- Redis returns `PONG`.
- Postgres shows an Alembic revision.
- No startup crash or repeated upstream refusal appears in recent logs.

### 6. Post-Deploy Changelog Push

If this was a user-facing versioned deploy, publish the same version into the in-app release-note
stream after the health checks pass. Do not push the raw technical changelog. First compare the
previous stable release to the new release and compress the update into 2 to 4 user-facing bullets
that focus on visible changes and stability gains. Keep the title and bullets in English unless the
user explicitly requests a different language:

```bash
cd /Users/lyw/Desktop/finance
python3 scripts/push_release_note_from_changelog.py \
  --origin https://your-server-origin \
  --admin-password 'your-admin-password' \
  --api-token 'your-api-token' \
  --title 'User-facing title' \
  --content $'- First core change\n- Second core change'
```

Use `$asset-tracker-changelog-push-sop` if the user asks specifically to push or verify the
release-note message.

### 7. Failure Triage

- If `/api/health` returns `502`, inspect `backend` first. Do not stop at compose status alone.
- If `backend` logs stop at `Waiting for application startup.` without `Application startup complete`, treat startup as failed.
- If Postgres is healthy but Alembic is missing or migration logs error, stop and surface the exact migration failure.
- If deploy health is green but changelog push fails, do not claim the release workflow is complete.

## Output Contract

When using this skill, respond with:

- A short preflight summary and risk level.
- Exact copy-paste commands for the current situation.
- A concise success or failure verdict backed by health checks, logs, and changelog-push status when applicable.
- One short clarifying question only if a critical assumption is unknown.

---
name: asset-tracker-production-ssh
description: Use when the user wants to SSH into the finance--tracker production server, inspect the live repo, run remote git pull or docker compose commands, or verify backend, worker, nginx, Postgres, and Redis on production.
---

# Asset Tracker Production SSH

## Overview

Use this skill for direct production host access for the finance--tracker project.

## Defaults

- SSH alias: `asset-tracker-aws`
- Backing host: `ubuntu@54.215.104.198`
- Remote repo path: `~/finance--tracker`
- Local repo path: `/Users/lyw/Desktop/finance`
- Local env file for secrets and deploy defaults: `.env.release-deploy.local`

Do not store passwords in this skill. Keep secrets in `.env.release-deploy.local` or local keychain-only tooling.

## Standard Commands

Check remote repo state:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && git status --short --branch && git rev-parse HEAD'
```

Pull `main` fast-forward only:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && git checkout main && git pull --ff-only origin main'
```

Rebuild and restart the production stack:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build --remove-orphans'
```

Verify health:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && docker compose -f docker-compose.yml -f docker-compose.production.yml ps && curl -k -fsS https://127.0.0.1/api/health && echo && docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T redis redis-cli ping && docker compose -f docker-compose.yml -f docker-compose.production.yml exec -T postgres sh -lc '\''psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select * from alembic_version;"'\'''
```

Inspect recent logs:

```bash
ssh asset-tracker-aws 'cd ~/finance--tracker && docker compose -f docker-compose.yml -f docker-compose.production.yml logs --tail=120 backend worker nginx'
```

## Notes

- Prefer the SSH alias `asset-tracker-aws` over raw `ubuntu@54.215.104.198` in commands and env files.
- The saved SSH user is expected to be in the `docker` group; use plain `docker compose` commands.
- Local production health checks go through nginx at `https://127.0.0.1/api/health` with `curl -k`.
- If non-interactive SSH keys are unavailable, the local deploy scripts may still use the alias together with `ASSET_TRACKER_SERVER_SSH_PASSWORD` from `.env.release-deploy.local`.
- For full versioned deploys with GitHub release verification and in-app broadcast, use `$asset-tracker-release-deploy-sop`.
- For routine pull/rebuild/health-check operations, use `$asset-tracker-server-update-sop`.

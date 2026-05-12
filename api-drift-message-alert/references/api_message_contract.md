# API Drift Message Contract

## APIs

- `POST /api/auth/login`: admin login with cookie session.
- `POST /api/feedback`: create feedback message for current user (here: admin).
- `GET /api/admin/feedback`: list feedback for admin review.
- `POST /api/admin/feedback/{feedback_id}/close`: close stale system notices.

## Required env

- `FEEDBACK_API_BASE_URL`
- `FEEDBACK_ADMIN_USER`
- `FEEDBACK_ADMIN_PASSWORD`
- `FEEDBACK_API_TOKEN` (optional)

## Input dependency

- Drift checker output: `.codex/api-drift/latest.json`
- Message dedupe state: `.codex/api-drift/message-state.json`

## Dedupe

- Use per-day notification key (day + kind + threshold + fingerprint + summary hash).
- If notification key equals previous key, skip publish by default.
- Use `--force` to bypass dedupe.

## Channel policy

- API drift alerts/status are admin-only feedback messages.
- Product/user release notes continue to use release-note publish flow and are not modified by this skill.

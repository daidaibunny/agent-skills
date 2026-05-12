# API Drift Risk Policy

## High Risk

- Endpoint unreachable, timeout, or non-JSON.
- Previously existing contract paths are missing.
- Treat as potential future crash risk for adapter logic.

## Medium Risk

- New contract paths are detected while old paths still exist.
- Usually non-breaking but should be reviewed before release.

## Low / None

- No structural drift relative to last successful baseline.

## Baseline Strategy

- Baseline updates automatically on healthy or medium drift runs.
- For high-risk drift, baseline is frozen by default so alerts keep surfacing.
- Use `--allow-baseline-reset` only after manual review.

## Alert Strategy

- `API_DRIFT_ALERT_THRESHOLD` controls when alert is raised (`high` by default).
- `API_DRIFT_EXIT_NONZERO_ON_ALERT=1` marks scheduled run as failed when alert is raised.
- Publish database station-message alerts through
  [$api-drift-message-alert](/Users/lyw/.codex/skills/api-drift-message-alert/SKILL.md).

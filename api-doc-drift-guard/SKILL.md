---
name: api-doc-drift-guard
description: Run daily API drift checks for backend and external market-data dependencies, compare latest contracts against stored baseline, and report potential future crash risk before provider/API changes break runtime logic.
---

# API Doc Drift Guard

## Overview

Use this skill when you need to monitor API contract drift and detect potential future crashes caused by upstream API or documentation changes.

## Workflow

1. Load project env (`.env.codex-feedback-automation.local`) so base URL and tokens are available.
  - Optional: set `FEEDBACK_OPENAPI_URL` to include OpenAPI/doc endpoint drift checks.
  - If `FEEDBACK_OPENAPI_URL` is absent, the doc target is skipped automatically.
2. Run the checker script:

```bash
python3 /Users/lyw/.codex/skills/api-doc-drift-guard/scripts/check_api_drift.py \
  --env-file /Users/lyw/Desktop/finance/.env.codex-feedback-automation.local \
  --state-file /Users/lyw/Desktop/finance/.codex/api-drift/state.json \
  --report-dir /Users/lyw/Desktop/finance/.codex/api-drift/reports \
  --latest-json /Users/lyw/Desktop/finance/.codex/api-drift/latest.json \
  --retain-days 30 \
  --retain-count 90
```

3. Read report and classify risk:
- `high`: possible future crash (missing paths, endpoint unavailable, invalid JSON).
- `medium`: additive drift; verify parser compatibility.
- `none`: contract stable.

4. If `high` appears:
- Do not ignore it.
- Open a fix task for adapter compatibility.
- Keep baseline frozen (default behavior) until fix is confirmed.

## Alerting

- Built-in alert trigger uses risk threshold:
  - default `API_DRIFT_ALERT_THRESHOLD=high` (only high risk alerts),
  - optional `medium` (high/medium both alert),
  - optional `none` (always alert).
- Built-in automation-visible alert:
  - default `API_DRIFT_EXIT_NONZERO_ON_ALERT=1`,
  - script exits non-zero when alert is needed, so scheduled run is visibly failed in inbox.
- Use database station-message alerting via
  [$api-drift-message-alert](/Users/lyw/.codex/skills/api-drift-message-alert/SKILL.md),
  not webhook.

## Output

- Markdown report: `/Users/lyw/Desktop/finance/.codex/api-drift/reports/api-drift-YYYYMMDD-HHMMSS.md`
- Latest JSON summary: `/Users/lyw/Desktop/finance/.codex/api-drift/latest.json`
- Baseline state: `/Users/lyw/Desktop/finance/.codex/api-drift/state.json`

## Retention

- Default cleanup is enabled:
  - Remove reports older than `30` days.
  - Keep at most newest `90` report files.
- You can tune it in automation:
  - More strict: `--retain-days 14 --retain-count 30`
  - Disable retention: `--retain-days 0 --retain-count 0`

## Minimal-Request Policy

- The checker performs one request per monitored endpoint.
- Historical-chart checks are represented by lightweight sample requests.
- The checker updates baseline only when safe; high-risk drift keeps prior baseline for persistent alerting.

## References

- Target definitions: [references/targets.json](references/targets.json)
- Risk policy: [references/risk-policy.md](references/risk-policy.md)

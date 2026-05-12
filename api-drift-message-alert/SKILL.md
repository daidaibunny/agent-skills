---
name: api-drift-message-alert
description: Publish API drift results as admin-only feedback messages in database. Use when daily drift check finishes and you need immediate admin notification (including no-change heartbeat) without sending to all users.
---

# API Drift Message Alert

## Overview

Convert API drift detection results into admin-only feedback messages stored in database.

## Workflow

1. Ensure drift result exists at `.codex/api-drift/latest.json`.
2. Run message publisher script to evaluate threshold and publish one admin message daily:

```bash
python3 /Users/lyw/.codex/skills/api-drift-message-alert/scripts/publish_api_drift_alert_message.py \
  --env-file /Users/lyw/Desktop/finance/.env.codex-feedback-automation.local \
  --latest-json /Users/lyw/Desktop/finance/.codex/api-drift/latest.json \
  --message-state-file /Users/lyw/Desktop/finance/.codex/api-drift/message-state.json \
  --threshold high \
  --timezone Asia/Shanghai
```

3. Read JSON output:
- `published`: new admin-only status message created.
- `duplicate_skipped`: same-day same-result already sent, skip duplicate.
- `dry_run`: preview message body only.

## Behavior Rules

- Do not use webhook.
- API drift channel uses feedback APIs and targets `admin` only.
- Send heartbeat even when no alert (`无变化`) once per day.
- Deduplicate by daily notification key to avoid repeated identical sends.
- Auto-close previous unresolved system messages by default to prevent backlog growth.
- System messages are closed via admin close endpoint and should not rely on reply flow.
- Do not modify user-facing release-note workflow.

## References

- API and dedupe contract: [references/api_message_contract.md](references/api_message_contract.md)

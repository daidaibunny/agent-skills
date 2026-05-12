---
name: feedback-approval-session
description: One-by-one feedback triage and approval gate for admin feedback queues. Use when running daily review of unresolved feedback, requiring exactly one question at a time, draft implementation plan/patch/reply, and waiting for explicit command `批准并执行 #ID` before any code mutation or user reply.
---

# Feedback Approval Session

## Overview
Run the daily feedback review loop for unresolved items. Process one feedback item at a time and stop at the approval gate before any mutation.

## Workflow
1. Load environment variables.
2. Fetch unresolved feedback and select one target item.
  - Default mode excludes system tickets (`SYSTEM_*`, monitor/agent generated items).
  - Use `--include-system` only for dedicated system-ops triage.
3. Ask exactly one question about that item and wait.
4. Produce three sections:
- `修复计划`
- `候选补丁`
- `拟发送给用户的回复草稿`
5. Wait for explicit approval command: `批准并执行 #ID`.
6. If approval is missing or malformed, stop and do not mutate files, push, or reply.

## Commands
Use the bundled script to fetch unresolved feedback:

```bash
python3 scripts/fetch_open_feedback.py --all
python3 scripts/fetch_open_feedback.py --pick-latest
python3 scripts/fetch_open_feedback.py --feedback-id 123
# Include system tickets explicitly when needed:
python3 scripts/fetch_open_feedback.py --all --include-system
```

Required environment variables:
- `FEEDBACK_API_BASE_URL`
- `FEEDBACK_ADMIN_USER`
- `FEEDBACK_ADMIN_PASSWORD`

Optional:
- `FEEDBACK_API_TOKEN`
- `http_proxy`
- `https_proxy`

## Approval Gate Rules
- Treat `批准并执行 #ID` as the only execution command.
- Ensure `#ID` matches the feedback item currently being discussed.
- If IDs do not match, reject execution and ask for a corrected approval command.
- Keep user reply in draft state until approval arrives.

## Failure Handling
- On login/network/API failure, output a blocking diagnosis and stop.
- On empty queue, report no unresolved feedback and stop.
- Never attempt fallback mutation paths before approval.

## References
- Read `references/approval_flow.md` for control flow details.
- Read `references/api_contract.md` for endpoint contracts and payloads.

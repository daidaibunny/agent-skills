---
name: feedback-reply-closer
description: Send approved admin replies to feedback and close items through existing admin feedback API endpoints. Use after successful code/test/git execution when user-facing reply draft has been reviewed and approved with `批准并执行 #ID`.
---

# Feedback Reply Closer

## Overview
Send an approved reply to a specific feedback item and mark it closed in one API call.

## Workflow
1. Validate approval command and feedback ID.
2. Load approved reply draft.
3. Login as admin via API.
4. Call reply endpoint with `close=true`.
5. Output API result for audit.

## Commands
```bash
python3 scripts/reply_and_close_feedback.py \
  --approval-text "批准并执行 #123" \
  --feedback-id 123 \
  --reply-text "已定位问题，修复已上线，请刷新后重试。"
```

Or from file:

```bash
python3 scripts/reply_and_close_feedback.py \
  --approval-text "批准并执行 #123" \
  --feedback-id 123 \
  --reply-file /path/to/reply.txt
```

## Safety Rules
- Never send replies without approval validation.
- Only send replies for user-origin feedback (`source=USER`); system tickets should be closed/classified without reply.
- Never close feedback when reply text is empty.
- If API fails, report failure and keep item unresolved.

## References
Read `references/reply_template.md` for drafting standards.

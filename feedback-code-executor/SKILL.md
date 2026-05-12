---
name: feedback-code-executor
description: Execute approved feedback implementation changes after explicit approval command validation. Use when approval text `批准并执行 #ID` is present, code must be changed and tested, and git commit/push must happen with proxy safeguards.
---

# Feedback Code Executor

## Overview
Execute code changes only after strict approval validation. Enforce test-first safety and git push proxy policy.

## Workflow
1. Validate approval command and feedback ID match.
2. Ensure working tree is ready and target branch exists or is created.
3. Apply implementation command.
4. Run test command list.
5. Commit only if tests pass and changes exist.
6. Push using proxy wrapper when requested.

## Commands
```bash
python3 scripts/apply_and_test.py \
  --approval-text "批准并执行 #123" \
  --feedback-id 123 \
  --workdir /Users/lyw/Desktop/finance \
  --apply-cmd "<implementation command>" \
  --test-cmd "<test command>" \
  --commit-message "fix: address feedback #123"

bash scripts/push_with_proxy.sh /Users/lyw/Desktop/finance
```

## Safety Rules
- Never run mutation commands without approval validation.
- Stop when tests fail.
- Stop when commit produces no changes.
- Never send user replies here; use the reply closer skill after successful push.

## References
Read `references/git_policy.md` before running commands.

# Git Policy

## Branch
Use `codex/feedback-fix-<id>-<yyyymmdd>`.

## Required Order
1. Validate approval command.
2. Apply code changes.
3. Run tests.
4. `git add .`
5. `git commit -m "fix: ..."`
6. Push with proxy (`http_proxy` and `https_proxy`).

## Blocking Rules
- If tests fail, stop and do not commit.
- If push fails, stop and do not send user reply.
- If no changes exist after apply phase, stop and report.

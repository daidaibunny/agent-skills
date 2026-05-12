# Approval Flow

## Goal
Run a daily unresolved-feedback loop with strict approval gating.

## Steps
1. Fetch unresolved feedback list.
2. Select one feedback item.
3. Ask one clarifying question and wait.
4. Draft:
- fix plan
- candidate patch
- user reply draft
5. Wait for exact approval command: `批准并执行 #ID`.
6. Verify approved ID matches the selected feedback ID.
7. Hand over to execution and reply skills.

## Stop Conditions
- Missing credentials.
- Login/API failure.
- No unresolved feedback.
- Approval command missing or ID mismatch.

## Never Do Before Approval
- Edit project files.
- Run commit/push.
- Send admin reply.
- Close feedback item.

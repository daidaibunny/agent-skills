# Changelog + GitHub Release Workflow

## Goal
When user asks for changelog/update release, produce a synchronized release result:
- changelog entry written
- git tag created
- GitHub Release published
- URL returned to user

## Inputs
- `repo_path`
- `version` (`x.y.z`)
- `title`
- user-facing `notes`

## Invariants
1. Tag is always `v<version>`.
2. `CHANGELOG.md` heading version equals tag version.
3. Changelog includes GitHub release URL (`.../releases/tag/v<version>`).
4. No publish before explicit user confirmation.

## Output Contract (before execution)
Show these 4 sections in chat:
1. 当前版本快照
2. changelog 草稿
3. GitHub Release 计划（tag / url）
4. 请确认是否发布

## Output Contract (after execution)
Return:
- commit SHA
- tag
- GitHub Release URL
- changelog path

## Blockers
Stop execution and report blocker if any of these fail:
- tracked changes exist in working tree
- tag already exists
- version already exists in changelog
- `gh` not installed/authenticated
- remote repo slug cannot be resolved

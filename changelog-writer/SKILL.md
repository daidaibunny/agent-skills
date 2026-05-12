---
name: changelog-writer
description: Run the full release update workflow when the user asks to "写 changelog", "发版本", or "发布更新". The workflow must keep version/tag aligned, update CHANGELOG.md, create git tag vX.Y.Z, publish GitHub Release, and return the release URL for user visibility.
---

# Changelog Writer

## Trigger
Use this skill when the user asks to write changelog, publish a version, or release an update.

## Required Outcome
One release operation must produce all of the following in one workflow:
1. `CHANGELOG.md` new version block
2. matching git tag `vX.Y.Z`
3. GitHub Release created from the same version/tag
4. release URL shown back to user

Release writing defaults:
- Write the `CHANGELOG.md` entry in English.
- Write the GitHub Release title and notes in English.
- Keep release copy in English unless the user explicitly asks for another language.

## Workflow
1. Collect repo/version context:
```bash
cd <repo_path>
git status --short --branch
git tag --sort=-version:refname | head
gh release list --limit 10 --json tagName,name,isDraft,isPrerelease,publishedAt,url
```
2. Draft release notes in chat and show exactly 4 blocks:
- `当前版本快照`
- `changelog 草稿`
- `GitHub Release 计划（tag / url）`
- `请确认是否发布`
3. Wait for explicit confirmation (recommended command): `确认发布 vX.Y.Z`.
4. Before execution, preview a deterministic plan in chat:
- target commit
- target tag `vX.Y.Z`
- `CHANGELOG.md` entry to publish
- GitHub release title and notes

All previewed release text should already match the final English wording that will be published.
5. After confirmation, execute publish workflow:
```bash
cd <repo_path>
git add CHANGELOG.md
git commit -m "chore(release): publish vX.Y.Z"
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
gh release create vX.Y.Z --title "<title>" --notes "<notes markdown>"
```
6. Return execution result with:
- commit SHA
- tag
- GitHub Release URL
- changelog write path

## Guardrails
- Tag must be `v<version>` and must match changelog version.
- Changelog entry must include GitHub Release URL.
- If working tree has tracked changes, stop and ask user whether to clean/stash/commit first.
- If `gh` is missing or not authenticated, stop and report blocker; do not fake success.
- Do not publish release without explicit confirmation.
- Do not reference helper scripts that do not exist in the target repo.

## References
- Read `references/changelog_workflow.md` for output contract and failure policy.

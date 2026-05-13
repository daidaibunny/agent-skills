---
name: knowledge-base-ingest
description: Use this skill only when the user explicitly asks to ingest, process, file, or import a raw source file that already exists under raw/. The source must be a local file path (for example raw/llm/article.md), not a URL. If the user provides a URL such as a WeChat article link, do not load this skill — load knowledge-base-clip instead.
---

# Knowledge Base Ingest

Ingest one user-provided raw source into the personal knowledge base. This is a write
workflow. Do not run it for ordinary knowledge-base reference requests.

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

## Preconditions

- The user must explicitly ask to ingest a source.
- The source must be under `raw/<domain>/` or an approved scoped vault such as
  `raw/<domain>/<scope>/`.
- Treat `raw/` as user-owned. Read raw files, but do not edit them.
- The source itself may be modified or untracked because the user just captured it.
  Include that exact raw source in the ingest commit.
- New files under `raw/assets/` may be local attachments captured with the source.
  Include only assets that are referenced by the source or clearly part of the same
  capture batch.

## Fixed Output Contract

For one raw source, create or update exactly these wiki surfaces in the matching wiki
scope:

- `<wiki-scope>/<source-slug>_summary.md`
- `<wiki-scope>/concept.md`
- `<wiki-scope>/entity.md`
- `<wiki-scope>/index.md`
- `wiki/index.md`
- `wiki/log.md`

Do not create per-concept files, per-entity files, `synthesis` pages, or `query-answer`
pages.

## Obsidian-Safe Format

- Use vault-root Obsidian links, such as `[[wiki/<domain>/concept#Name|Name]]` or
  `[[wiki/<domain>/<scope>/concept#Name|Name]]`.
- Use explicit asset embeds: `![[raw/assets/file.webp]]`.
- In YAML, quote Obsidian links.
- Use source fields only when non-empty:
  - `source_paths`
  - `source_urls`
  - `source_assets`
  - `source_pages`
- Source summaries use `source_paths` and `source_urls`; concept/entity/domain pages use
  `source_pages` when grounded in summaries.

## Path Variables

- `<raw-source>` is the exact user-provided source path.
- `<wiki-scope>` is the exact wiki vault directory that matches `<raw-source>`.
- Domain vault mapping:
  - `raw/<domain>/<source>` maps to `wiki/<domain>`.
  - The summary path is `wiki/<domain>/<source-slug>_summary.md`.
- Approved scoped vault mapping:
  - `raw/<domain>/<scope>/<source>` maps to `wiki/<domain>/<scope>`.
  - The summary path is `wiki/<domain>/<scope>/<source-slug>_summary.md`.
- If a deeper scoped vault is approved later, preserve the full nested path on both
  sides: `raw/<domain>/<scope>/<subscope>/<source>` maps to
  `wiki/<domain>/<scope>/<subscope>`.
- In every `rg` command, replace `<wiki-scope>` with the full matching wiki directory,
  not just the parent domain. Replace `<raw-source>` with the full raw source path.

## Ingest Protocol

1. Identify the source path and matching wiki scope from the path mapping rules above.
2. Check `git status --short -- <raw-source> raw/assets` to see whether the raw source
   or captured assets are uncommitted.
3. If the source is markdown, scan local asset references before writing:

   ```bash
   rg -n '!\\[\\[|!\\[[^]]*\\]\\(' <raw-source>
   ```

4. Read `wiki/index.md`, including the tag registry.
5. Read the matching wiki scope's `index.md`, `concept.md`, and `entity.md`.
6. Search for related existing concepts, entities, and summaries before writing.
7. Read the raw source.
8. Create or update one summary named `<source-slug>_summary.md` with Obsidian-safe
   source metadata.
9. Update `concept.md` for reusable ideas, mechanisms, methods, claims, or problem
   types from the source.
10. Update `entity.md` for named people, organizations, products, models, tools,
   benchmarks, datasets, papers, projects, or named workflows.
11. Update the matching scope index and global index.
12. If a new tag is necessary, first check `wiki/index.md` for a similar tag. Reuse an
    existing tag when possible. If creating a tag, add it to the tag registry.
13. Prepend an `ingest` entry to `wiki/log.md`.
14. Commit and push directly to `origin/main`, including the raw source and relevant
    `raw/assets/` attachments from this ingest.

## Naming Rules

Source summary slug:

```text
raw/<domain>/<source>
wiki/<domain>/<source-slug>_summary.md

raw/<domain>/<scope>/<source>
wiki/<domain>/<scope>/<source-slug>_summary.md
```

- Lowercase the title.
- Replace spaces with hyphens.
- Remove unnecessary punctuation.
- Always end source summaries with `_summary.md`.
- Keep `concept.md` and `entity.md` as the only concept and entity files in the
  matching wiki scope.

## Tags

Default page tags are:

- the matching domain or scoped-vault tag
- the page type tag

Do not invent synonym tags for the same idea. Maintain canonical tags in
`wiki/index.md`.

## Search Commands

List existing scope pages:

```bash
rg --files <wiki-scope> | sort
```

Use the full nested scope, for example `wiki/<domain>/<scope>`, when the source belongs
to a scoped vault.

Search the matching wiki scope first:

```bash
rg -n --glob '*.md' '<term-or-phrase>' <wiki-scope>/
```

Keep the trailing slash and point it at the full nested scope to avoid searching the
parent domain by accident.

Search concept and entity registries:

```bash
rg -n --glob 'concept.md' '<term-or-phrase>' <wiki-scope>/
rg -n --glob 'entity.md' '<term-or-phrase>' <wiki-scope>/
```

For scoped vaults, these commands should read the scoped `concept.md` and `entity.md`,
not the parent domain registries.

Search the broader wiki only when cross-domain links are likely:

```bash
rg -n --glob '*.md' '<term-or-phrase>' wiki/
```

Find local assets referenced by an Obsidian-clipped markdown source:

```bash
rg -o '!\\[\\[[^]]+\\]\\]' <raw-source>
```

Use the exact raw file path, including all approved nested scope segments.

List uncommitted raw source and attachment candidates:

```bash
git status --short -- <raw-source> raw/assets
```

## Required Updates

After writing wiki pages, update:

```text
<wiki-scope>/index.md
wiki/index.md
wiki/log.md
```

Use this log heading format:

```text
## [YYYY-MM-DD] ingest | Source Title
```

When updating `wiki/log.md`, read only the top of the file:

```bash
sed -n '1,15p' wiki/log.md
```

Insert the new entry immediately after `# Log`. Do not read, rewrite, delete, or reorder
older log entries.

## Git

**Before any commit, verify the repository state:**

```bash
branch=$(git branch --show-current)
if [ "$branch" != "main" ]; then
  echo "ERROR: not on main branch (current: $branch). Aborting."
  exit 1
fi
if [ -n "$(git status --porcelain)" ] && ! git diff --quiet; then
  # Uncommitted changes exist — review before proceeding
fi
```

```bash
git status --short --branch
git add <raw-source> <referenced-raw-assets> <wiki-files>
git commit -m "ingest: <short source title>"
git push origin main
```

Do not add unrelated uncommitted raw files, assets, or `.obsidian/` changes unless they
belong to the current ingest.

## Cross-Domain Synthesis Matrix

After updating `concept.md` or `entity.md` with new or modified entries, update the
synthesis status matrix in `wiki/wow-moment/index.md`:

1. Read the matrix if `wiki/wow-moment/index.md` exists (it may not if the wow-moment
   domain has not been created yet — skip this step in that case).
2. In the `## Synthesis Status` table, set the affected domain's status to `pending` and
   update the `Concepts Since` column to reflect what changed.
3. If the affected domain does not yet have a row in the matrix, add one with status
   `pending`.
4. Include this change in the commit.

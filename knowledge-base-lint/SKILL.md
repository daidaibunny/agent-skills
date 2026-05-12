---
name: knowledge-base-lint
description: Use this skill only when the user explicitly asks to lint, health-check, audit, or clean up the personal knowledge base.
---

# Knowledge Base Lint

Run a scoped health check over the personal knowledge base. Do not run it for ordinary
reference requests.

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

## Preconditions

- The user must explicitly ask for linting, a health check, audit, consistency review, or
  cleanup.
- The user may scope lint to one domain, several domains, or the whole wiki.
  - Prefer concrete findings and proposed edits over long reports.
  - Do not edit `raw/`; only report raw-source issues or update wiki pages that reference
    raw sources.
  - Do not modify wiki files until the user approves the specific finding.
- Two sub-scopes exist:
  - **Freshness**: `lint freshness <domain>` or `lint freshness --all` for content
    freshness checks.
  - **Wow Moment Synthesis**: `lint wow-moment <domain>` or `lint wow-moment --all`
    for cross-domain knowledge synthesis. This is delegated to the
    `knowledge-base-wow-moment-synthesize` skill. Defaults to incremental mode.

## Lint Protocol

1. Determine the scope from the user request.
2. Read `wiki/index.md`, including the tag registry.
3. Read only the relevant wiki scope's `index.md`, `concept.md`, and `entity.md` files,
   or all domain indexes and registries for a broad lint.
4. Run the fixed search commands below.
5. Identify structural issues, tag issues, semantic duplicates, and missing registry
   entries.
6. Output findings one by one in the conversation with concrete proposed edits.
7. Wait for user approval before modifying files.
8. After approval, update affected pages and indexes.
9. Prepend a `lint` entry to `wiki/log.md`.
10. Commit and push directly to `origin/main`.

## Path Variables

- `<wiki-scope>` is the exact wiki vault directory being linted.
- Domain vaults use `wiki/<domain>`.
- Approved scoped vaults use `wiki/<domain>/<scope>`.
- If a deeper scoped vault is approved later, preserve the full nested path, for example
  `wiki/<domain>/<scope>/<subscope>`.
- In every `rg` command, replace `<wiki-scope>` with the full scope under review.
  Lint the parent domain only when the user asks for that parent scope or a broader
  whole-wiki lint.

## Search Commands

List wiki pages:

```bash
rg --files wiki | sort
```

This broad command is for whole-wiki lint only.

List selected scope pages:

```bash
rg --files <wiki-scope> | sort
```

For scoped vault lint, use the full nested vault path.

List raw sources:

```bash
rg --files raw | sort
```

Find non-summary markdown pages outside the fixed files:

```bash
rg --files <wiki-scope> | rg -v '/(index|concept|entity)\\.md$|_summary\\.md$'
```

Run this against the selected full scope so allowed files are checked at that vault
level.

Find source summaries with wrong names:

```bash
rg --files <wiki-scope> | rg 'summary|source|article|paper' | rg -v '_summary\\.md$'
```

Run this against the selected full scope so nested vault summaries are not mixed with
the parent domain.

Find obsolete page types or terms:

```bash
rg -n --glob '*.md' 'type: (synthesis|query-answer)|## Open Questions|synthesis page|query-answer' wiki/ AGENTS.md
```

Find Obsidian links that omit the vault-root `wiki/` path:

```bash
rg -n --pcre2 --glob '*.md' '\\[\\[(?!wiki/|raw/)[^]|#]+/' wiki/ AGENTS.md
```

Find obsolete mixed source frontmatter:

```bash
rg -n --glob '*.md' '^sources:' wiki/
```

Find unresolved markers:

```bash
rg -n --glob '*.md' 'TODO|TBD|FIXME|unclear|unknown|needs source|citation needed' wiki/
```

Find unregistered or inconsistent tags:

```bash
rg -n --glob '*.md' '^  - [a-z0-9-]+$' wiki/
```

Find possible semantic duplicates by heading:

```bash
rg -n --glob 'concept.md' '^## ' <wiki-scope>/
rg -n --glob 'entity.md' '^## ' <wiki-scope>/
```

These commands inspect the fixed registries inside the selected vault scope.

Find repeated terms in summaries that may need registry entries:

```bash
rg -n --glob '*_summary.md' '<repeated-concept-or-entity>' <wiki-scope>/
```

Use the full nested scope path before comparing possible duplicates across broader
scopes.

## Check Items

- Each domain has exactly one `index.md`, one `concept.md`, and one `entity.md`.
- Each approved scoped vault has exactly one `index.md`, one `concept.md`, and one
  `entity.md`.
- No unapproved subfolders exist inside domains.
- Each raw source has at most one matching `_summary.md`.
- Source summaries always end in `_summary.md`.
- No per-concept or per-entity files remain.
- No `synthesis` or `query-answer` pages remain.
- No `## Open Questions` sections remain; use `## Insights`.
- Domain indexes link their `concept.md`, `entity.md`, and summaries.
- Important concepts mentioned in summaries are present in `concept.md`.
- Important entities mentioned in summaries are present in `entity.md`.
- Concept and entity sections have canonical names and aliases when useful.
- Related concepts and entities use explicit section links.
- Tags in page frontmatter exist in the registry in `wiki/index.md`.
- Obsidian links use vault-root paths such as `[[wiki/<domain>/concept#Name|Name]]` or
  `[[wiki/<domain>/<scope>/concept#Name|Name]]`.
- Source metadata uses `source_paths`, `source_urls`, `source_assets`, and
  `source_pages`; do not use mixed `sources`.
- Synonym tags are merged into one canonical tag.
- Contradictions or uncertainty are marked.
- Semantically duplicated concepts or entities are merged, cross-linked, or distinguished.

## Required Updates

For each finding, present:

```text
Finding:
Files:
Issue:
Proposed edit:
Expected impact:
```

After approved fixes, update:

```text
<wiki-scope>/index.md
wiki/index.md
wiki/log.md
```

Use this log heading format:

```text
## [YYYY-MM-DD] lint | Scope
```

When updating `wiki/log.md`, read only the top of the file:

```bash
sed -n '1,15p' wiki/log.md
```

Insert the new entry immediately after `# Log`. Do not read, rewrite, delete, or reorder
older log entries.

## Git

```bash
git status --short --branch
git add <relevant-files>
git commit -m "lint: <short scope>"
git push origin main
```

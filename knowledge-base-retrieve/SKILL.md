---
name: knowledge-base-retrieve
description: Use this skill when the user asks to reference the personal knowledge base.
---

# Knowledge Base Retrieve

Retrieve only the knowledge base context needed for the current task. This skill is
read-only. Do not edit files, ingest sources, lint the wiki, update logs, or use Git.

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

## Read Protocol

1. If the user names a domain or approved scoped vault, read the matching
   `wiki/<domain>/index.md` or `wiki/<domain>/<scope>/index.md` first.
2. If no domain is named, read `wiki/index.md` and choose the relevant domain index.
3. Read the matching `concept.md` and `entity.md` only as needed.
4. Use the fixed `rg` patterns below from the knowledge base root to find matching
   source summaries.
5. Read only the smallest useful set of sections or pages.
6. Use the retrieved context in the current task and cite the wiki pages used.

Use `source_paths`, `source_urls`, `source_assets`, and `source_pages` in frontmatter to
trace evidence. Read `raw/` only when the user asks for original-source verification.

## Path Variables

- `<wiki-scope>` is the exact wiki vault directory chosen from the user's request.
- Domain vaults use `wiki/<domain>`.
- Approved scoped vaults use `wiki/<domain>/<scope>`.
- If a deeper scoped vault is approved later, preserve the full nested path, for example
  `wiki/<domain>/<scope>/<subscope>`.
- In every `rg` command, replace `<wiki-scope>` with the full matching wiki directory.
  Do not shorten a scoped vault search to its parent domain unless cross-scope context is
  explicitly needed.

## Search Commands

Prefer selected-scope search:

```bash
rg -n --glob '*.md' '<term-or-phrase>' <wiki-scope>/
```

For scoped vaults, search the full nested scope path first.

Search fixed registries directly:

```bash
rg -n --glob 'concept.md' '<term-or-phrase>' <wiki-scope>/
rg -n --glob 'entity.md' '<term-or-phrase>' <wiki-scope>/
```

These commands target the fixed registries inside the selected vault scope.

Search only source summaries:

```bash
rg -n --glob '*_summary.md' '<term-or-phrase>' <wiki-scope>/
```

This keeps source-summary reads limited to the selected vault scope.

Find summaries that point to a raw source or URL:

```bash
rg -n 'source_paths:|source_urls:|raw/|https?://' <wiki-scope>/
```

Use the full nested scope path so raw-source traces are scoped correctly.

If the domain is unknown or results are insufficient, search the wiki:

```bash
rg -n --glob '*.md' '<term-or-phrase>' wiki/
```

To list candidate pages in a selected scope before reading them:

```bash
rg --files <wiki-scope> | sort
```

For a nested vault, list the nested vault directory itself, not the parent domain.

Use short terms first, then refine. Read only the files surfaced by `wiki/index.md`, the
selected scope index, or these `rg` commands.

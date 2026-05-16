---
name: knowledge-base-domain
description: Use when the user asks to add, rename, merge, or remove a domain or approved scoped vault in the knowledge base.
---

# Knowledge Base Domain

Create, rename, merge, or remove a domain or approved scoped vault. This is a write
workflow. Do not run it for ordinary knowledge-base queries or single-source ingests.

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

## Preconditions

- The user must explicitly ask to add, rename, merge, or remove a domain or scoped vault.
- A new domain must have a clear name and purpose distinct from existing domains.
- A new scoped vault must belong to an existing parent domain and have a clear scope
  boundary.
- The assistant must confirm the proposed change before modifying anything.

## Protocol

### Step 1 — Confirm the Change

1. Present exactly what will happen:

   ```text
   Proposed change: add domain <name>
   Purpose: <one-line purpose>
   Will create:
     - raw/<name>/
     - wiki/<name>/index.md
     - wiki/<name>/concept.md
     - wiki/<name>/entity.md
   Will update:
     - AGENTS.md (domain list)
     - wiki/index.md (structure, tag registry, domains, fixed registries,
       source summaries, raw sources)
     - wiki/log.md
   ```

2. For a scoped vault, additionally list the parent domain index update.
3. For rename/merge/remove, list all files that move or are deleted.
4. **Do not proceed without explicit user confirmation.**

### Step 2 — Create Directory Structure

For a new domain:

```bash
mkdir -p raw/<domain>
mkdir -p wiki/<domain>
```

For a new scoped vault:

```bash
mkdir -p raw/<domain>/<scope>
mkdir -p wiki/<domain>/<scope>
```

### Step 3 — Create Fixed Pages

Create `wiki/<domain>/index.md` (or `wiki/<domain>/<scope>/index.md` for a scoped vault)
with this template:

```markdown
---
title: <Domain Name>
type: domain
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
tags:
  - <domain-tag>
  - domain
---

# <Domain Name>

## Purpose

<One-paragraph statement of what this domain covers and why it exists.>

## Source Types

<Types of sources expected in this domain: articles, papers, documentation, threads,
videos, etc.>

## Fixed Pages

- [[wiki/<domain>/concept|<domain> concepts]]
- [[wiki/<domain>/entity|<domain> entities]]
<For scoped vaults, use the full nested path.>

## Sources

| Source | URL | Type | Frequency | Last Checked |
|--------|-----|------|-----------|---------------|
| - | - | - | - | - |

Source types: docs, research-blog, arxiv-feed, github-repo, community, newsletter.
Frequency: daily, weekly, monthly.

## Source Summaries

<Empty — populated by Ingest and Research.>

## Insights

<Initial observations, if any. Otherwise leave empty.>
```

Create `wiki/<domain>/concept.md` (or scoped vault equivalent) with this template:

```markdown
---
title: <Domain Name> Concepts
type: concept
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
tags:
  - <domain-tag>
  - concept
---

# <Domain Name> Concepts
```

Create `wiki/<domain>/entity.md` (or scoped vault equivalent) with this template:

```markdown
---
title: <Domain Name> Entities
type: entity
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
tags:
  - <domain-tag>
  - entity
---

# <Domain Name> Entities
```

### Step 4 — Update AGENTS.md

1. Add the domain name to the domain list in the `## Domains` section.
2. If a scoped vault, add it to the `Approved scoped vaults` list.
3. Update the directory contract diagram with the new paths.

### Step 5 — Update wiki/index.md

For a new domain:

1. **Structure diagram**: add the new `wiki/<domain>/` subtree with `index.md`,
   `concept.md`, `entity.md`.
2. **Tag Registry**: add a new domain tag under `### Domain Tags`:

   ```markdown
   - `<domain-tag>` - <one-line description of the domain's scope.>
   ```

3. **Domains section**: add a link and date:

   ```markdown
   - [[wiki/<domain>/index|<domain>]] - Updated <YYYY-MM-DD>.
   ```

4. **Fixed Registries section**: add concept and entity links:

   ```markdown
   - [[wiki/<domain>/concept|<domain> concepts]]
   - [[wiki/<domain>/entity|<domain> entities]]
   ```

5. **Source Summaries section**: add the placeholder if there are existing summaries, or
   leave it for future Ingest/Research.
6. **Raw Sources section**: same treatment.

For a scoped vault, add child entries under the parent domain in each section.

For rename/merge/remove: update all affected links, tags, and references across all
files listed above. Ensure no broken Obsidian links remain.

### Step 6 — Update wiki/log.md

Prepend an entry:

```text
## [YYYY-MM-DD] maintenance | <action> domain <name>
```

Read only the top of the file first:

```bash
sed -n '1,15p' wiki/log.md
```

Insert the new entry immediately after `# Log`.

### Step 7 — Commit and Push

**Before any commit, verify the repository state:**

```bash
branch=$(git branch --show-current)
if [ "$branch" != "main" ]; then
  echo "ERROR: not on main branch (current: $branch). Aborting."
  exit 1
fi
```

```bash
git add raw/<domain>/ wiki/<domain>/ AGENTS.md wiki/index.md wiki/log.md
git commit -m "maintenance: <action> domain <name>"
git push origin main
```

## Domain Naming Rules

- Use lowercase kebab-case for domain names in paths: `machine-learning`, not
  `Machine Learning` or `machine_learning`.
- Domain tags use the same name as the directory.
- Frontmatter titles use human-readable names: `Machine Learning`, not
  `machine-learning`.
- Scoped vault directories follow the same convention: `<domain>/<scope>`.

## Obsidian-Safe Format

- Use vault-root Obsidian links: `[[wiki/<domain>/concept#Name|Name]]`.
- For scoped vaults: `[[wiki/<domain>/<scope>/concept#Name|Name]]`.
- Quote Obsidian links in YAML frontmatter.
- Domain tag additions follow the existing tag format in `wiki/index.md`.

## Rename / Merge / Remove

For destructive operations:

1. List every file that will be created, moved, or deleted.
2. Search for all Obsidian links referencing the old name:

   ```bash
   rg -n '\[\[wiki/<old-name>' wiki/ AGENTS.md
   ```

3. Confirm with the user before any file deletion or renaming.
4. Update all cross-references in concept.md, entity.md, and summaries across all
   domains.
5. Never force-push or use `git rm` without user confirmation.

## Skill Backup

After creating or modifying a domain, ensure both copies of all knowledge-base skills
are in sync:

- `~/.codex/skills/knowledge-base-*/SKILL.md` (global, read by Codex/OpenCode)
- `wiki/knowledge-base/skills/knowledge-base-*/SKILL.md` (repository backup)

## Cross-Domain Synthesis Matrix

When creating, renaming, or removing a domain, update the wow-moment synthesis matrix.
See [[wiki/knowledge-base/wow-moment-synthesize_summary|wow-moment-synthesize]] for the protocol.

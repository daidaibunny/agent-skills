---
name: knowledge-base-clip
description: Clip remote content from a URL into the knowledge base. Use when the user sends a URL from WeChat or other messaging platforms and wants to capture, format, and ingest content that requires browser automation to access. Handles content extraction, image downloading, domain matching, approval gating, and automatic ingest.
---

# Knowledge Base Clip

Clip remote content from a URL (typically WeChat Official Account shared articles) into
the knowledge base. This is a write workflow that combines content extraction, asset
downloading, approval gating, and automatic ingest.

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

## Preconditions

- The user must send a URL to be clipped (typically via WeChat bot routed through Hermes
  agent).
- A browser-capable agent must be available to open the URL and extract content from
  walled-garden sources that cannot be fetched with simple HTTP requests.
- Clip handles the full pipeline: extract content, download images, save to `raw/`,
  present for approval, and auto-trigger the standard Ingest protocol.
- Treat `raw/` as the capture destination. Clip writes formatted markdown and downloaded
  images there, following the same conventions as manual user capture.

## Clip Protocol

### Step 1 — Content Extraction

1. A browser-capable agent opens the URL and extracts:
   - Article title
   - Full article body text
   - Author name (if available in the article)
   - Publication date (if available in the article)
   - All image URLs referenced in the article content
2. Do not rely on user-provided metadata. Extract everything from the article itself.
3. Convert the article body to well-formed markdown:
   - Preserve heading hierarchy (`#`, `##`, `###`)
   - Preserve links with original URLs
   - Preserve lists (ordered and unordered)
   - Preserve blockquotes
   - Strip non-content elements (advertisements, navigation, recommended articles,
     comment sections)

### Step 2 — Image Download

1. Download every image referenced in the article content to `raw/assets/`.
2. Naming convention: `<source-slug>-<n>.<ext>`
   - `<source-slug>`: lowercase, hyphen-separated title slug
   - `<n>`: sequential number starting from 1
   - `<ext>`: original file extension (webp, png, jpg, gif)
3. Replace remote image URLs in the markdown with vault-root embed references:
   `![[raw/assets/<source-slug>-<n>.<ext>]]`
4. Skip decorative images, icons, tracking pixels, and other non-content elements.
5. Do not take screenshots. Download actual image files from their source URLs.

### Step 3 — Save Raw Source

1. Format the source file name: `<title-slug>.md`
   - Lowercase the title
   - Replace spaces with hyphens
   - Remove unnecessary punctuation
2. Save the markdown to `raw/<domain>/<title-slug>.md`.
   - For scoped vaults: `raw/<domain>/<scope>/<title-slug>.md`
3. The domain is determined in Step 4. If the domain is not yet confirmed, use a
   temporary placeholder and rename after confirmation.
4. Commit the raw source and downloaded assets:

   ```bash
   git add raw/<domain>/<title-slug>.md raw/assets/<source-slug>-*
   git commit -m "clip: capture <title-slug>"
   ```

### Step 4 — Domain Matching

1. Read `wiki/index.md` for the current domain structure and tag registry.
2. Read the content of the extracted article.
3. Infer the best-matching existing domain from the content:
   - Search for matching concepts across all domain concept registries.
   - Search for matching entities across all domain entity registries.
   - Match against domain descriptions in the tag registry.
4. **Always present the inferred domain to the user for confirmation.** Do not write to a
   domain without explicit user approval.
5. If no existing domain clearly matches:
   - Reference the `knowledge-base-domain` skill for domain creation.
   - Present the current domain structure to the user for context (see Domain Structure
     Reference below).
   - Ask the user: "No matching domain found. Current domains are listed above. Would
     you like to create a new domain, or assign this to an existing one?"

### Step 5 — Approval Gate (MANDATORY)

1. After content extraction, image download, and domain inference, compose an approval
   preview. The preview must include:
   - Article title
   - Proposed domain (with a request to confirm or change)
   - Brief content summary (one to two sentences)
   - Number of images downloaded
   - Publication date (if extracted)
   - Author (if extracted)
2. Send the preview to the user via WeChat (through Hermes agent).
3. **Wait for explicit user confirmation.** Do not proceed to Step 6 without it.
4. Acceptable confirmation responses:
   - "确认" or "confirm": proceed with the proposed domain
   - "<domain>" or "<domain>/<scope>": change domain and proceed
   - "拒绝" or "reject": abort the clip, optionally clean up saved raw files

### Step 6 — Automatic Ingest

After user approval, run the standard Ingest protocol (`knowledge-base-ingest` skill)
with the confirmed domain:

1. Verify the raw source is saved at `raw/<confirmed-domain>/<title-slug>.md`.
2. Read `wiki/index.md`, especially the tag registry.
3. Read the matching wiki scope's `index.md`, `concept.md`, and `entity.md`.
4. Search for related existing concepts, entities, and source summaries.
5. Create exactly one source summary: `<wiki-scope>/<title-slug>_summary.md`
   - Include `source_paths` pointing to the raw source.
   - Include `source_urls` pointing to the original URL.
   - Include `source_assets` listing downloaded images.
6. Update `concept.md` in the matching wiki scope for new or refined concepts.
7. Update `entity.md` in the matching wiki scope for new or refined entities.
8. Update the matching scope `index.md`:
   - Add the new source summary to the source list.
   - If the source URL is worth ongoing monitoring, add to the `## Sources` table.
9. Update `wiki/index.md`: source summaries section, raw sources section, tag registry
   if new tags were added (check for existing equivalents first).
10. Prepend a `clip` entry to `wiki/log.md`:

    ```text
    ## [YYYY-MM-DD] clip | Article Title → <domain>
    ```

    Read only the top of the file first:

    ```bash
    sed -n '1,15p' wiki/log.md
    ```

    Insert the new entry immediately after `# Log`. Do not read, rewrite, delete, or
    reorder older log entries.

11. Commit and push:

    ```bash
    git add <all-wiki-files>
    git commit -m "clip: <article title> → <domain>"
    git push origin main
    ```

### Step 7 — Report

After completion, report back to the user via WeChat (through Hermes agent):
- Article title
- Domain ingested to
- Summary page path as an Obsidian link
- Concepts added (if any)
- Entities added (if any)

## Path Variables

- `<domain>`: Confirmed target domain (for example `llm`, `finance`)
- `<scope>`: Approved scoped vault segment when applicable (for example `quant`, `agent`)
- `<title-slug>`: Lowercase, hyphen-separated article title for file naming
- `<wiki-scope>`: Full wiki directory matching the domain and scope
- `<source-slug>`: Same as `<title-slug>`, used for asset naming

## Search Commands

Search for matching concepts across all domains:

```bash
rg -n --glob 'concept.md' '<term>' wiki/
```

Search for matching entities across all domains:

```bash
rg -n --glob 'entity.md' '<term>' wiki/
```

List existing source summaries to avoid duplicates:

```bash
rg --files <wiki-scope> | sort
```

## Domain Structure Reference

When presenting domain options to the user, use this structure:

```text
wiki/
├── finance/          — Investing, personal finance, asset allocation, risk
│   └── quant/        — Quantitative finance research and trading systems
├── personal/         — Goals, habits, reflection, psychology
├── llm/              — Large language models, prompting, evaluations
│   └── agent/        — Autonomous AI agent systems and architectures
├── career/           — Career direction, skills, portfolio, opportunities
├── health/           — Health sources, routines, measurements
├── knowledge-base/   — This repository's workflow, schema, and maintenance
│   └── skills/       — Agent skills library and runtime tools
└── projects/         — Concrete scoped projects, decisions, artifacts
```

## Naming Rules

- Source summary slug: lowercase, hyphen-separated, always ends in `_summary.md`.
- Raw source slug: lowercase, hyphen-separated, `.md` extension.
- Asset naming: `<source-slug>-<n>.<ext>` where `<n>` starts at 1.

## Required Updates

After clip completes, these surfaces must be updated:

```text
<wiki-scope>/<title-slug>_summary.md   (new source summary)
<wiki-scope>/concept.md                (new or updated concepts)
<wiki-scope>/entity.md                 (new or updated entities)
<wiki-scope>/index.md                  (source list, sources table)
wiki/index.md                          (global index, tag registry if needed)
wiki/log.md                            (clip entry)
```

## Git

After Step 3 (raw source and assets only):

```bash
git add raw/<domain>/<title-slug>.md raw/assets/<source-slug>-*
git commit -m "clip: capture <title-slug>"
```

After Step 6 (all wiki changes):

```bash
git add <wiki-files>
git commit -m "clip: <article title> → <domain>"
git push origin main
```

## Cross-Domain Synthesis Matrix

After the automatic Ingest step (Step 6) updates `concept.md` or `entity.md` in the
target domain, update the synthesis status matrix in `wiki/wow-moment/index.md`:

1. Read the matrix if `wiki/wow-moment/index.md` exists (it may not if the wow-moment
   domain has not been created yet — skip this step in that case).
2. In the `## Synthesis Status` table, set the affected domain's status to `pending`
   and update the `Concepts Since` column.
3. If the affected domain does not yet have a row, add one with status `pending`.
4. Include this change in the Step 6 commit.

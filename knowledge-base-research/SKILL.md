---
name: knowledge-base-research
description: Use when the user asks to research a topic, fill knowledge gaps, or batch-discover and ingest high-quality sources into the knowledge base.
---

# Knowledge Base Research

Research a topic by discovering high-quality web sources, presenting them for approval,
then batch-ingesting approved sources. This is a write workflow. Do not run it for
ordinary knowledge-base queries.

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

## Preconditions

- The user must explicitly ask to research a topic, fill gaps in a domain, or
  batch-discover sources.
- The assistant may write to `raw/` and `raw/assets/` during Research as an explicit
  exception. Outside Research, the normal raw/ write restriction applies.

## Source Discovery Strategy (Priority Order)

When searching for supplementary high-quality sources, follow this priority.
Network accessibility data is maintained in the `knowledge-base-clip` skill
(Network Capabilities Reference) and this project's `AGENTS.md` → Network Access.

1. **Stack Exchange API** — `api.stackexchange.com/2.3/search?order=desc&sort=votes&intitle=<term>&site=stackoverflow`. Works without proxy. Use `webfetch` for direct question URLs (CAPTCHA-free). Do NOT use the web search page (triggers CAPTCHA).
2. **Industry blogs** — Fingerprint.com, Cloudflare Blog, Mozilla Hacks, Google Security Blog. Direct HTTP, no proxy needed.
3. **Official docs** — RFC, W3C, MDN, protocol specifications. Always accessible.
4. **fxtwitter API** — `GET api.fxtwitter.com/<user>/status/<tweet-id>` for resolving X/Twitter tweet content and quoted tweets.
5. **Playwright browser** — Reserve for X/Twitter (logged-in browsing) and WeChat (walled-garden). For X/Twitter: must use a persistent browser profile with login cookies. For all Playwright sessions: inject the Anti-Detection Bootstrap from the `knowledge-base-clip` skill before navigating.
6. **Skip Reddit** — Blocked ("Please wait for verification"). Do not attempt.
7. **Skip Google Search** — JS redirect loop. Do not attempt.
8. **Do not use curl** — Prefer `webfetch` for HTTP content, Playwright for browser-required content.

### Quality Filters

Apply these filters to candidate sources before presenting to the user:

- **Authority**: Named author or organization with domain track record.
- **Recency**: Published or substantively updated within the last 2 years.
- **Depth**: Original analysis, data, or synthesis — not surface aggregation.
- **Relevance**: Directly addresses the research topic.
- **Deduplicate**: Check against existing source summaries in the target scope before proposing.

## Research Protocol

### Step 1 — Confirm Domain and Scope

1. From the user's topic, identify candidate domain(s): one of the existing domains
   (`finance`, `personal`, `llm`, `career`, `health`, `knowledge-base`, `projects`) or an
   approved scoped vault (`finance/quant`, `knowledge-base/skills`).
2. If no existing domain clearly matches, propose adding a new domain via the
   `knowledge-base-domain` skill first. Do not silently create new domains.
3. **Present the proposed domain mapping and ask the user to confirm.** Do not proceed
   without explicit confirmation.

### Step 2 — Discovery

1. Read `wiki/<domain>/index.md` for existing context and the `## Sources` section.
   Start searches from registered sources when they exist.
2. Search the web for high-quality sources. Prioritize:
   - Official documentation for relevant tools, frameworks, or APIs.
   - Authoritative blog posts from recognized experts or organizations.
   - Peer-reviewed papers (arXiv, conferences).
   - Widely-cited community resources with clear authorship.
3. Apply quality filters:
   - **Authority**: named author or organization with domain track record.
   - **Recency**: published or substantively updated within the last 2 years.
   - **Depth**: original analysis, data, or synthesis — not surface aggregation.
   - **Relevance**: directly addresses the research topic.
4. Deduplicate against existing source summaries in the target scope. Skip sources that
   are already well-covered.

### Step 3 — Approval Gate (MANDATORY)

1. Present candidate sources as a compact list:

   ```text
   ## Candidate Sources for "<topic>" → <domain>

   1. **Title** — URL
      Type: article | paper | docs | thread | other
      Summary: one sentence on what it covers.
      Quality: brief authority / recency / depth note.

   2. ...
   ```

2. Ask the user to approve, reject specific items, or request more.
3. Do **NOT** proceed to Step 4 without explicit user approval.

### Step 4 — Fetch and Save Raw Sources

For each approved source:

1. Fetch the full web page content.
2. **If paywalled**: attempt to extract publicly visible content. Save what is
   accessible. Mark the source summary with a `## Paywall` note recording what is
   missing. This source becomes a candidate for Lint freshness follow-up.
3. Convert to markdown and save to `raw/<domain>/<title-slug>.md`. Use the same
   naming convention as user-clipped sources: lowercase, hyphens, no punctuation.
4. Scan the source for image references. For each image:
   - Download to `raw/assets/<source-slug>-<n>.<ext>`.
   - Reference in the raw source as `![[raw/assets/<file>]]`.
5. Commit the raw source and assets:

   ```bash
   git add raw/<domain>/<title-slug>.md raw/assets/<source-slug>-*
   git commit -m "research: capture <title-slug>"
   ```

### Step 5 — Create Source Summaries

For each approved source, follow the standard Ingest protocol exactly:

1. Read `wiki/index.md`, especially the tag registry.
2. Read the matching wiki scope's `index.md`, `concept.md`, and `entity.md`.
3. Search for related existing concepts, entities, and summaries.
4. Read the raw source saved in Step 4.
5. Create exactly one source summary named `<title-slug>_summary.md` with:
   - `source_urls` pointing to the original URL.
   - `source_paths` pointing to `raw/<domain>/<title-slug>.md`.
   - `source_assets` listing any downloaded images under `raw/assets/`.
   - Full summary: core claim, key facts, relevant concepts, relevant entities,
     contradictions, implications.
6. Use vault-root Obsidian links and explicit asset embeds following the standard
   conventions.

### Step 6 — Update Registries

For each source, update the matching wiki scope:

1. **concept.md**: add or update sections for reusable ideas, mechanisms, methods,
   claims, or problem types introduced or changed by the source.
2. **entity.md**: add or update sections for named people, organizations, products,
   models, tools, benchmarks, datasets, papers, projects, or workflows.
3. Use explicit section anchors: `[[wiki/<domain>/concept#Name|Name]]`.

### Step 7 — Update Indexes

After processing all approved sources:

1. Update `wiki/<domain>/index.md`:
   - Add each new source summary to the source list.
   - If a source URL is worth ongoing monitoring, add it to the `## Sources` table
     (create the section if it does not exist).
2. Update `wiki/index.md`:
   - Source summaries section.
   - Raw sources section.
   - Tag registry if new tags were added (check for existing equivalents first).
3. If a source is paywalled, ensure the domain index notes it under a `## Paywalled
   Sources` subsection for Lint attention.

### Step 8 — Log and Push

1. Prepend a batch `research` entry to `wiki/log.md`:

   ```text
   ## [YYYY-MM-DD] research | <Topic> — <N> sources → <domain>
   ```

   Read only the top of the file first:

   ```bash
   sed -n '1,15p' wiki/log.md
   ```

   Insert the new entry immediately after `# Log`.

2. Commit and push:

   ```bash
   git add <all-wiki-files>
   git commit -m "research: <topic> — <N> sources → <domain>"
   git push origin main
   ```

### Step 9 — Report

Summarize in conversation:
- Number of sources ingested.
- New concepts added (list canonical names).
- New entities added (list canonical names).
- URLs added to the domain `## Sources` table.
- Any paywalled sources flagged for Lint follow-up.
- Any contradictions found across sources.

## Path Variables

- `<domain>` is the confirmed target domain from Step 1.
- For approved scoped vaults, use the full nested path:
  - Raw: `raw/<domain>/<scope>/<title-slug>.md`
  - Summary: `wiki/<domain>/<scope>/<title-slug>_summary.md`
  - Assets: `raw/assets/<scope>-<source-slug>-<n>.<ext>`

## Source Registry Convention

Each domain index `## Sources` section uses this table:

```markdown
## Sources

| Source | URL | Type | Frequency | Last Checked |
|--------|-----|------|-----------|---------------|
```

- `Frequency`: daily, weekly, or monthly.
- Add discovered high-value URLs during Research. Update `Last Checked` during Lint.

## Paywall Handling

1. Attempt to extract any publicly visible content (abstract, preview, metadata).
2. Save accessible content as the raw source.
3. In the source summary, add:

   ```markdown
   ## Paywall

   Full content behind paywall at <URL>. Accessible content saved.
   Missing: <description of what was inaccessible>.
   ```

4. Add the source to the domain index under a `## Paywalled Sources` subsection.
5. During Lint freshness checks, revisit paywalled sources to see if they are now
   accessible or have public alternatives.

## Deduplication

- Before proposing a candidate source, search existing summaries in the target scope:

  ```bash
  rg -n --glob '*_summary.md' '<key-term>' wiki/<domain>/
  rg -n 'source_urls:' wiki/<domain>/
  ```

- Skip sources whose content is already substantially covered by an existing summary.

## Git

**Before any commit, verify the repository state:**

```bash
branch=$(git branch --show-current)
if [ "$branch" != "main" ]; then
  echo "ERROR: not on main branch (current: $branch). Aborting."
  exit 1
fi
```

```bash
# After Step 4 (raw sources only):
git add raw/<domain>/<title-slug>.md raw/assets/<source-slug>-*
git commit -m "research: capture <title-slug>"

# After Step 8 (all wiki changes):
git add <wiki-files>
git commit -m "research: <topic> — <N> sources → <domain>"
git push origin main
```

## Cross-Domain Synthesis Matrix

After updating `concept.md` or `entity.md` with new or modified entries during Step 6,
update the synthesis status matrix in `wiki/wow-moment/index.md`:

1. Read the matrix if `wiki/wow-moment/index.md` exists (it may not if the wow-moment
   domain has not been created yet — skip this step in that case).
2. In the `## Synthesis Status` table, set each affected domain's status to `pending`
   and update the `Concepts Since` column.
3. If an affected domain does not yet have a row, add one with status `pending`.
4. Include this change in the Step 8 commit.

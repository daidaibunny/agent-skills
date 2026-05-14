---
name: auto-ingest
description: Process the watchlist ingest manifest — read raw/daily-digest/ingest-manifest.json, run the standard Ingest workflow for each high-score (≥8) raw source file, update domain registries, and commit. Use when Hermes processes the daily auto-ingest queue.
---

# Auto Ingest

Process high-score watchlist items through the standard Ingest workflow.

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

## Workflow

### 1. Read Manifest

```
Check {KB_PATH}/raw/daily-digest/ingest-manifest.json
If not found or empty → [SILENT] (nothing to process)
Limit: process at most 5 entries per run (to stay within token budget)
```

### 2. For Each Entry

For each raw file listed in the manifest, run the standard **Ingest** protocol
(as defined in `knowledge-base-ingest` skill):

```
1. Read the raw source file at `raw_path`
2. Read wiki/index.md for tag registry context
3. Read wiki/{domain}/index.md, concept.md, entity.md
4. Create source summary: wiki/{domain}/{title-slug}_summary.md
5. Update wiki/{domain}/concept.md — add or update concepts from the source
6. Update wiki/{domain}/entity.md — add or update entities from the source
7. Update wiki/{domain}/index.md — add source summary to list
8. Update wiki/index.md — add to source summaries and raw sources sections
9. Prepend an `ingest` entry to wiki/log.md
10. Commit and push: `git add -A && git commit -m "ingest: {title}" && git push`
```

### 3. Cleanup

After all entries are processed, update the manifest to remove processed items.
If all items processed, delete the manifest file.

### 4. Report

Return a summary of what was ingested and which registries were updated.

## Important Rules

- Work directly on `main` branch
- Always use `http_proxy=http://127.0.0.1:10808 https_proxy=http://127.0.0.1:10808` for git push
- Follow the Ingest protocol strictly — create source summaries, update concept/entity, commit
- Limit to 5 entries per run to avoid excessive token consumption
- If a raw file no longer exists, skip and log a warning
- Never create `synthesis` or `query-answer` pages
- Use YAML frontmatter with proper `title`, `type`, `created`, `updated`, `tags`, `source_paths`, `source_urls`

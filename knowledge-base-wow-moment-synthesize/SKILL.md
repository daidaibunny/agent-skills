---
name: knowledge-base-wow-moment-synthesize
description: Synthesize cross-domain connections in the knowledge base to discover non-obvious, high-value insights. Use as a lint subprocess after ingest, research, or clip operations to find surprising combinations of knowledge across domains that create actionable economic or intellectual value. Defaults to incremental mode: only checks domains with new content since the last synthesis run.
---

# Knowledge Base Wow Moment Synthesize

Synthesize cross-domain connections to discover wow moments: non-obvious combinations of
knowledge from different domains that together create actionable, economically valuable
insights. This is a lint subprocess. Do not run it for ordinary knowledge-base queries.

A wow moment is NOT a simple cross-reference ("concept A is similar to concept B").
Ordinary relationships are already recorded in each domain's concept and entity
registries. A wow moment is a multi-domain synthesis that creates something none of the
individual domains could produce alone.

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

## Preconditions

- This skill runs as a subprocess of `knowledge-base-lint`, triggered by
  `lint wow-moment <domain>` or `lint wow-moment --all`.
- Default mode is **incremental**: only check domain pairs where at least one domain has
  new or modified concepts or entities since the last synthesis check.
- A user may request full synthesis with `--all` or specify exact domains with
  `lint wow-moment <domain-a> <domain-b>`.
- The `wiki/wow-moment/` domain must exist. If it does not, create it using the
  `knowledge-base-domain` skill before proceeding. Confirm with the user first.

## Quality Bar (CRITICAL)

Do NOT record ordinary connections. Wow moments must meet at least one of these criteria:

1. **Method Migration**: A method from one domain directly solves a problem in another
   domain that currently lacks a solution.
2. **Conceptual Isomorphism**: Two domains describe the same underlying mechanism with
   different terminology, and recognizing this unlocks new capabilities.
3. **Gap Bridging**: A knowledge gap or open question in one domain has an answer that
   already exists in another domain.
4. **Contradiction Resolution**: Two domains make conflicting claims about the same
   phenomenon, and resolving this conflict produces a deeper understanding.
5. **Combinatorial Innovation**: Concepts from two or more domains combine to form a new
   actionable idea that has clear economic or practical value.
6. **Economic Value Synthesis**: Disparate knowledge pieces from multiple domains connect
   to form a complete, actionable business model, product idea, or investment thesis.
   For example: finance (business model) + internet commerce (execution strategy) +
   social media (distribution channel) + e-commerce (platform) = a complete business
   opportunity.

If a candidate does not clearly demonstrate one of these six types, do not record it.

## Cross-Domain Synthesis Matrix

`wiki/wow-moment/index.md` maintains a synthesis status matrix tracking which domain
pairs have been checked:

```markdown
## Synthesis Status

| Domain | Status | Last Synthesis | Concepts Since |
|--------|--------|---------------|----------------|
| finance | pending | 2026-05-10 | 2 new concepts (2026-05-13 ingest) |
| llm | done | 2026-05-12 | 0 |
| ... | ... | ... | ... |
```

When a write operation (ingest, research, clip) adds or modifies concepts or entities
in a domain, it must update this matrix: set the domain's status to `pending` and note
what changed. When a lint structural check modifies concepts or entities, it does the
same.

When synthesizing incrementally, only process domains with `pending` status. Pair each
pending domain against all other domains (both pending and done, since a done domain
may not have been checked against this newly-pending domain).

After synthesis completes for a domain, update its status to `done`.

## Synthesis Protocol

### Step 1 — Determine Scope

1. If the user runs `lint wow-moment`, default to incremental mode:
   - Read `wiki/wow-moment/index.md` for the synthesis status matrix.
   - Identify all domains with `pending` status.
   - If none are pending, report "No domains with new content since last synthesis run."
     and stop.
2. If the user runs `lint wow-moment --all`, set scope to all domain pairs.
3. If the user runs `lint wow-moment <domain-a> <domain-b>`, check only that pair.
4. For incremental and --all modes, skip pairs already recorded as `done` unless there
   have been changes since the last check.

### Step 2 — Read Domain Concepts (Lightweight)

For each domain in scope, read only the concept names and one-line definitions from
`wiki/<domain>/concept.md` and `wiki/<domain>/entity.md`. Do not read full source
summaries at this stage.

```bash
rg -n '^## |Canonical name:|### Definition' wiki/<domain>/concept.md
```

### Step 3 — Cross-Domain Matching

For each domain pair, compare their concept and entity lists:

1. Identify concepts from domain A whose mechanisms, goals, or constraints resemble those
   in domain B at a structural level (not surface keywords).
2. Prioritize unexpected connections — pairs of domains that seem unrelated on the
   surface (for example `finance/quant` and `health`).
3. For candidate matches, read the full concept sections from both domains to verify the
   depth of the connection.

### Step 4 — Filter by Quality Bar

Apply the six wow-moment criteria from the Quality Bar section. Reject candidates that:
- Are only surface-level keyword overlaps.
- Describe ordinary cross-references already captured in Related Concepts.
- Do not produce an actionable or insightful synthesis.

### Step 5 — Check for Existing Wow Moments

Before recording a new finding:

1. Search `wiki/wow-moment/entity.md` for semantically similar existing wow moments:

   ```bash
   rg -n '^## ' wiki/wow-moment/entity.md
   ```

2. For each existing wow moment whose domains overlap with the candidate, read the full
   entry and compare.
3. If an existing wow moment already captures the same insight:
   - Determine whether the existing entry can be updated with a minor addition (a new
     source reference, an additional domain, a refined insight) rather than creating a
     duplicate.
   - Only create a new entry if the new insight is meaningfully distinct.
4. Present to the user: "An existing wow moment (`[[wiki/wow-moment/entity#Name|Name]]`)
   covers a similar connection. I can either: (a) update it with this new angle, or
   (b) create a separate entry. Which do you prefer?"

### Step 6 — Present Findings for Approval

Present each candidate wow moment one at a time:

```text
## Wow Moment Candidate

**Type**: Method Migration | Conceptual Isomorphism | Gap Bridging |
Contradiction Resolution | Combinatorial Innovation | Economic Value Synthesis

**Domains involved**: <domain-a>, <domain-b>, [<domain-c>...]

**The connection**:
<Concise description of the synthesis — what does the combination of these domains
produce that neither could alone?>

**Source grounding**:
- [[wiki/<domain-a>/concept#ConceptName|Concept]]
- [[wiki/<domain-b>/entity#EntityName|Entity]]

**Value**: <What actionable insight, economic value, or intellectual breakthrough does
this produce?>

**Action**: Reply "record" to save, "skip" to move on, or provide a revised description.
```

### Step 7 — Record Approved Wow Moments

For each approved finding:

1. Add an entry to `wiki/wow-moment/entity.md`:

   ```markdown
   ## <Wow Moment Name>

   Canonical name: <Wow Moment Name>

   ### What It Is

   <Description of the synthesized insight.>

   ### Domains Involved

   - [[wiki/<domain-a>/index|<domain-a>]]
   - [[wiki/<domain-b>/index|<domain-b>]]

   ### Source Grounding

   - [[wiki/<domain-a>/concept#Concept|Concept]]
   - [[wiki/<domain-b>/concept#Concept|Concept]]
   <Include source summaries if the insight draws from specific sources.>

   ### Value

   <Actionable economic or intellectual value.>

   ### Related Concepts

   <Cross-domain concept links.>

   ### Related Entities

   <Cross-domain entity links.>
   ```

2. Update the original concepts in each domain's `concept.md`:
   - Add a cross-domain reference in the `### Related Concepts` section pointing to the
     wow moment.
   - Add a brief insight if the connection enriches the concept's understanding.

3. Update `wiki/wow-moment/concept.md` to reflect any recurring synthesis patterns
   discovered.

4. Add the entry to `wiki/wow-moment/index.md` under a `## Recorded Wow Moments` list:

   ```markdown
   - [[wiki/wow-moment/entity#<Name>|<Name>]] — <one-line summary>.
     Recorded <YYYY-MM-DD>.
   ```

### Step 8 — Update All Affected Domain Indexes

For each domain whose concept or entity registry was modified in Step 7, update the
domain's `index.md` to reflect the changes.

### Step 9 — Update Synthesis Status Matrix

In `wiki/wow-moment/index.md`, update the synthesis status for each domain processed:

```markdown
| Domain | Status | Last Synthesis | Concepts Since |
|--------|--------|---------------|----------------|
| <domain> | done | <YYYY-MM-DD> | 0 |
```

### Step 10 — Update Global Indexes and Log

1. Update `wiki/index.md`:
   - Source summaries section if new synthesized insights qualify.
   - Tag registry if new patterns warrant a new tag.
2. Prepend a `lint` entry to `wiki/log.md` (wow-moment runs as a lint subprocess):

   ```text
   ## [YYYY-MM-DD] lint | wow-moment-synthesize — <N> domains checked, <M> wow moments found
   ```

   Read only the top of the file first:

   ```bash
   sed -n '1,15p' wiki/log.md
   ```

   Insert the new entry immediately after `# Log`. Do not read, rewrite, delete, or
   reorder older log entries.

3. Commit and push:

   ```bash
   git add wiki/wow-moment/ wiki/<affected-domains>/ wiki/index.md wiki/log.md
   git commit -m "lint: wow-moment-synthesize — <M> findings across <N> domains"
   git push origin main
   ```

## Cross-Domain Matrix Interaction Protocol

This section defines how other write operations interact with the synthesis matrix.
Apply these interactions in the respective skill protocols.

### Ingest / Research / Clip

After updating `concept.md` or `entity.md` with new or modified entries, update the
synthesis status matrix:

1. Read `wiki/wow-moment/index.md` if it exists (the domain may not exist yet).
2. In the `## Synthesis Status` table, set the affected domain's status to `pending`
   and update the `Concepts Since` column.
3. If the domain does not yet have a row in the matrix, add one.
4. Include this change in the commit.

### Domain Management

When creating a new domain:
1. Add a row for the new domain in the synthesis status matrix with status `pending`.
When removing a domain:
1. Remove its row from the matrix.
2. Check `wiki/wow-moment/entity.md` for wow moments referencing the removed domain
   and flag them for review.

### Lint (Structural)

When a structural lint operation modifies `concept.md` or `entity.md` entries (merging
duplicates, adding missing entries, correcting cross-references), update the synthesis
status matrix the same way as Ingest.

## Path Variables

- `<domain>`: Domain directory name (for example `llm`, `finance`, `health`).
- `<scope>`: Approved scoped vault segment when applicable.

## Search Commands

Read concept registries (lightweight):

```bash
rg -n '^## |Canonical name:|### Definition' wiki/<domain>/concept.md
rg -n '^## |Canonical name:|### What It Is' wiki/<domain>/entity.md
```

Search for existing wow moments:

```bash
rg -n '^## ' wiki/wow-moment/entity.md
```

Search for semantic duplicates across wow moment entries:

```bash
rg -n --glob 'entity.md' '<term>' wiki/wow-moment/
```

## Required Updates

After synthesis completes, these surfaces must be updated:

```text
wiki/wow-moment/entity.md        (new or updated wow moment entries)
wiki/wow-moment/concept.md       (recurring synthesis patterns)
wiki/wow-moment/index.md         (synthesis status matrix, recorded wow moments list)
wiki/<domain>/concept.md         (cross-domain references for each affected domain)
wiki/<domain>/entity.md          (cross-domain references for each affected domain)
wiki/<domain>/index.md           (domain index updates)
wiki/index.md                    (global index, tag registry if new patterns added)
wiki/log.md                      (lint entry)
```

## Git

```bash
git add wiki/wow-moment/ wiki/<affected-domains>/ wiki/index.md wiki/log.md
git commit -m "lint: wow-moment-synthesize — <M> findings across <N> domains"
git push origin main
```

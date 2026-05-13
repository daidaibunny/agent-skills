---
name: knowledge-base-clip
description: Clip content from a URL into the knowledge base through browser automation. Use when the user sends a URL (for example a WeChat Official Account article link) and asks to clip, ingest, capture, or save it — even if the user says "ingest" followed by a URL, the URL means this must be clipped first. Also use when the user explicitly says "clip" followed by a URL. Handles content extraction, image downloading, domain matching, approval gating, and automatic ingest after the content has been saved to raw/.
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

## Platform-Specific Rules

### X / Twitter Platform

X platform tweets and threads require special handling because the author frequently
posts extended content ("pages") as replies to their own tweet, and high-value insights
also appear in non-author replies.

**Reply collection rule**: Always collect TWO categories of replies:

1. **Author's own replies**: The original author's replies in the thread. These often
   contain the author's numbered "pages" (1/n, 2/n, ...) that extend the main tweet
   into a full essay. These are the PRIMARY capture target.
2. **Highest-engagement non-author replies**: Identify the top 2-3 replies from other
   users with the most likes/retweets. These may contain valuable counterpoints,
   expansions, or practical applications of the original ideas.

**Critical rules for X extraction**:

- **ONE unified raw source**: Produce exactly ONE `.md` file per clip session. Never
  create separate files for individual replies. Combine the main tweet, author replies,
  and top non-author replies into a single well-structured document.
- **Expand replies first**: X requires clicking "Show replies" / "查看回复" to load
  the reply thread. Use Playwright to scroll through the page incrementally (X uses
  virtual scrolling — content outside the viewport is removed from DOM). Collect
  articles incrementally as you scroll.
- **Login required for replies**: X blocks unauthenticated access to reply threads.
  Ensure the browser profile has valid login cookies before extracting. If not logged
  in, ask the user to log in first.
- **Use fxtwitter API as supplement**: When quoted tweet content is truncated in the
  browser (X collapses long quoted tweets with "Show more"), use the fxtwitter API
  (`https://api.fxtwitter.com/<user>/status/<tweet-id>`) to retrieve the full tweet
  text including the complete quoted tweet body. This is the definitive way to resolve
  truncations.
- **Fix bare URLs**: After extraction, ensure all URLs are wrapped in markdown link
  syntax (`[text](url)`). Plain URLs adjacent to Chinese parentheses `（）` will cause
  the closing `）` to be incorrectly included as part of the URL when clicked.
- **Structure the output**:
  ```markdown
  # Title
  **来源**: [X / @author](url)
  **作者**: author info
  **日期**: date info

  ## 主帖
  (main tweet content)

  ## 作者回复（作者扩展页）
  **Reply 1 (1/n)** — topic
  > quoted content

  **Reply 2 (2/n)** — topic
  > quoted content

  ## 高价值回复（非作者）
  **@user1** (NN likes)
  > reply content

  **@user2** (NN likes)
  > reply content
  ```

**Extraction workflow for X**:

1. Navigate to the tweet URL with logged-in Playwright browser.
2. Wait for page render (3 seconds).
3. Close any login/signup dialogs (press Escape).
4. Scroll through the entire page in 2000px increments, at each step:
   - Click any "Show replies" / "查看回复" / "显示更多" buttons.
   - Wait for content to load (800ms).
   - Collect any author-tweet `article` elements not previously seen.
5. Collect ALL author tweets (check for `@handle` and display name in User-Name element).
6. For author replies that contain quoted tweets with truncated content (ends with
   "显示更多", "2." without following text, or bare "…"), resolve via fxtwitter API.
7. Identify top 2-3 non-author replies by engagement count.
8. Extract their full text (including any quoted content).
9. Format everything into the unified markdown structure above.
10. Submit for user domain confirmation, then follow standard Clip Protocol Step 3+.

### WeChat Official Account

WeChat Official Account articles (mp.weixin.qq.com) are the original primary target of
this skill. See Content Extraction below for the general Playwright workflow that applies
to WeChat and generic walled-garden sources.

## Content Extraction

### Primary: Playwright + Persistent Browser Profile

The primary extraction method uses Playwright with a persistent browser profile, mirroring
how Obsidian Web Clipper works: a logged-in browser opens the page, extracts the
fully-rendered DOM, and converts the content to markdown in-browser.

1. **Profile directory convention**:
   ```text
   ~/.hermes/browser-profiles/wechat/    # WeChat web (mp.weixin.qq.com)
   ~/.hermes/browser-profiles/x/         # X / Twitter
   ```
2. **Initial setup**: Open each platform URL once with the persistent profile, complete
   the login flow (WeChat: scan QR code with the WeChat app. X: enter credentials).
   Subsequent sessions reuse the stored cookies.
3. **Cookie maintenance**: The profile must be configured to persist cookies, local storage,
   and session data across restarts. This is the mechanism that avoids triggering CAPTCHA.
   When cookies expire and CAPTCHA reappears, do NOT cycle retries — fall through to the
   alternative below.
4. **Volume considerations**: This knowledge base is human-triggered (the user manually
   sends URLs from their phone). The access pattern is low frequency — a few articles per
   day at most, single-URL access, not bulk scraping. This pattern is unlikely to trigger
   aggressive anti-bot countermeasures that would risk account suspension.

After opening the page with the persistent profile:

1. Wait for the page to fully render (JavaScript-loaded content, lazy images).
2. Inject JavaScript to extract the article content from the DOM:
   - Identify the main content container using heuristics: `<article>`, `[role="main"]`,
     `.rich_media_content`, `.article-content`, or the largest text-dense element.
   - Extract: article title (`<h1>` or `og:title` meta), publication date, author name.
   - Strip non-content elements: navigation bars, sidebars, advertisements, comment
     sections, recommended articles, social sharing buttons.
   - Collect all `<img>` URLs from the content area. Skip tracking pixels, icons, and
     decorative images based on size and class names.
3. Convert the extracted HTML content to well-formed markdown in the browser:
   - Preserve heading hierarchy (`#`, `##`, `###`).
   - Preserve links with original URLs.
   - Preserve lists (ordered and unordered).
   - Preserve blockquotes and inline formatting.
4. **Detect truncated content**: After extraction, check whether the content appears
   truncated — for example the article body is substantially shorter than expected, ends
   with "登录后阅读全文" (log in to read the full article), "订阅继续阅读" (subscribe to continue),
   or shows only a preview paragraph with a paywall/login prompt. If truncated content is
   detected, record this in a `## Truncated Content Note` in the raw source file and flag
   it for manual completion later.

### Alternative: Jina Reader

If the Playwright primary path fails (CAPTCHA despite persistent profile, cookie expiry,
or browser unavailability), try Jina Reader as the sole alternative:

```text
https://r.jina.ai/<article-url>
```

Jina Reader converts accessible web pages to clean markdown with a single HTTP request.
It is lightweight and fast for publicly accessible content, but will also fail on
walled-garden pages that require login.

Try Jina Reader exactly ONCE. Do not cycle between Playwright and Jina — if one fails,
try the other once, then fast-fail. Do not use curl, search engines, or other approaches.

### Fast Failure

If BOTH primary (Playwright with persistent profile) and the single alternative
(Jina Reader) fail:

1. **Recognize failure signatures immediately**:
   - `mp.weixin.qq.com/mp/wappoc_appmsgcaptcha` (WeChat CAPTCHA)
   - Page title "环境异常" or "验证码" (WeChat environment check)
   - Any login wall, Cloudflare challenge, or JavaScript challenge page
   - Empty or near-empty content from Jina Reader
2. **Stop after at most 2 attempts total** (primary + one alternative).
3. **Report to the user via the approval channel**:
   ```text
   无法自动访问这篇文章。遇到了 [CAPTCHA 验证/登录墙]。
   替代方案：请将文章内容复制粘贴发送给我，或者手动在浏览器中完成验证后通知我重试。
   ```
4. Adhere to the agent's configured tool loop guardrails. Do not retry the same URL
   with slight variations.

### Truncated Content Handling

Some articles show only a partial preview before requiring login or subscription. After
content extraction (whether successful via Playwright or Jina Reader), check for
truncation signals:

- Article body under ~500 characters when the original is clearly longer
- Phrases like "登录后阅读全文", "订阅继续阅读", "扫码阅读全文", "阅读全文请点击"
- "Sign in to continue reading", "Subscribe to read the full article"
- A visible paywall or login prompt in the extracted content
- Jina Reader returning substantially less content than the page visibly contains

If truncated content is detected:

1. Save whatever content WAS successfully extracted to `raw/<domain>/<title-slug>.md`.
2. Add a `## Truncated Content Note` section at the top of the raw source file:
   ```markdown
   ## Truncated Content Note
   
   The full article requires login or subscription to access. Only the preview
   content has been saved. Images that were accessible have been downloaded. The
   complete article needs manual retrieval.
   
   Access requirement: [login / subscription / other]
   ```
3. Download any images that were accessible in the truncated portion.
4. Continue with the standard Clip protocol (domain matching, approval, ingest).
5. During the approval preview, inform the user: "注意：这篇文章仅提取了预览部分，完整内容需要登录/订阅后手动补充。"

## Clip Protocol

### Step 1 — Content Extraction

Content extraction follows the two-tier strategy defined in the Content Extraction
section above:

1. **Primary**: Use Playwright with a persistent browser profile to open the URL,
   extract content from the fully-rendered DOM, and convert to markdown in-browser.
   This mirrors the Obsidian Web Clipper approach.
2. **Alternative (exactly once)**: If primary fails (CAPTCHA, expired cookies), try
   Jina Reader (`https://r.jina.ai/<article-url>`) as the sole fallback.
3. **Fast-fail**: If both fail, report to the user and stop.
4. **Truncation check**: After extraction, verify the content is complete. If truncated,
   record a `## Truncated Content Note` in the raw source file.
5. Do not rely on user-provided metadata. Extract everything from the article itself.
6. **Image input capability check**: Before attempting to read or analyze images from
   the article (for OCR or content extraction), determine whether the active model
   supports image input.
   - If the model supports image input: optionally read key images to improve extraction
     quality.
   - If the model does NOT support image input (for example DeepSeek): skip all
     image-reading attempts.
   - Regardless of image input support, all content images must be downloaded to
     `raw/assets/` in Step 2.

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

### Step 8 — Research Extension (Context-Aware)

After the clip and ingest are complete, proactively evaluate whether the topic benefits
from supplementary high-quality sources. This step is NOT mandatory for every clip —
apply it when the clipped content covers a technical, academic, or professionally deep
topic where external references would add significant value.

**When to trigger Research Extension**:

- The clipped content covers a technical topic (e.g., browser fingerprinting, protocol
  design, cryptographic methods, software architecture).
- The content contains claims that would benefit from external validation or counterpoint.
- The topic has a rich body of high-quality material on StackOverflow, Reddit
  (r/programming, r/netsec, r/crypto, etc.), official documentation, or authoritative
  engineering blogs.
- The user explicitly requests deeper coverage.

**Research sources (quality-ordered)**:

1. Official documentation and specifications (RFC, W3C, IEEE, protocol specs).
2. StackOverflow highly-upvoted answers (score ≥ 50).
3. Reddit r/programming, r/netsec, r/crypto, r/MachineLearning — top-voted posts and
   comments with technical depth.
4. Authoritative engineering blogs (Cloudflare, Mozilla Hacks, Google Security Blog, etc.).
5. Academic papers (via arxiv.org or Google Scholar) when the topic warrants it.

**Research output**:

1. If highly relevant, substantive content is found, create an additional raw source at
   `raw/<domain>/<scope>/<topic-slug>-research-supplement.md` (or in the parent domain
   if no scope applies).
2. The research supplement must clearly distinguish:
   - The original clipped content source
   - Each external source with its URL and a one-sentence quality justification
   - Synthesized insights that bridge the original content and external findings
3. Run the standard Ingest protocol on the research supplement as a separate source
   summary `<topic-slug>-research-supplement_summary.md`.
4. In the research supplement's source summary, cross-reference the original clipped
   source summary.
5. Update the domain `concept.md` and `entity.md` with any new concepts or entities
   discovered through research.
6. If the research uncovers content that belongs to a different domain, propose
   creating a separate source in that domain to avoid scope confusion.

**Research Extension commit**:

```bash
git add raw/<domain>/<scope>/<topic-slug>-research-supplement.md wiki/<domain>/<scope>/<topic-slug>-research-supplement_summary.md
git commit -m "research: supplementary sources for <original-topic>"
git push origin main
```

Use `research` as the log type for research extension entries in `wiki/log.md`.

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

**Before any commit, verify the repository state:**

```bash
branch=$(git branch --show-current)
if [ "$branch" != "main" ]; then
  echo "ERROR: not on main branch (current: $branch). Aborting."
  exit 1
fi
```

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

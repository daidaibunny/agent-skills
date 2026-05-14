---
name: watchlist-monitor
description: Automated monitoring of high-value information sources defined in raw/watchlist/rules.yaml. Fetches content from RSS, APIs, Hacker News, and X/Twitter (via Playwright), scores items via free LLM provider chain with failover, and pushes notifications via Feishu Bot. Supports event-driven (stream) and polling (poll) source methods with hybrid push cadence (daily digest + real-time for score ≥ 9). Use when Hermes needs to run scheduled watchlist monitoring, when the user says "run watchlist", or when setting up automated content monitoring.
---

# Watchlist Monitor

Automated content monitoring, scoring, and push notification system for the personal
knowledge base. This skill defines the complete workflow executed by Hermes Agent on a
schedule.

## Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  rules.yaml  │────▶│  Fetch + Score  │────▶│  Feishu Bot  │
│  (KB raw/)   │     │  (Hermes cron)  │     │  → Phone     │
└──────────────┘     └─────────────────┘     └──────────────┘
```

## Prerequisites

Before running the monitor, Hermes must have:

1. **Knowledge base cloned** at a known path.
2. **Environment variables**:
   - `FEISHU_BOT_WEBHOOK_URL` — Feishu bot webhook for push delivery.
   - `GOOGLE_AI_STUDIO_API_KEY` — Google AI Studio API key (Priority 1 scoring).
   - `OPENROUTER_API_KEY` — OpenRouter API key (Priority 2+ scoring fallback).
   - `FRED_API_KEY` — (optional) FRED economic data API key.
3. **Playwright browser** installed and configured with a persistent profile
   (for X/Twitter scraping). See `## X/Twitter Scraping Setup` below.
4. **State directory** writable for `watchlist_state.json`.

## Configuration

The central configuration file is:

```
{knowledge_base_path}/raw/watchlist/rules.yaml
```

Read this file at startup and on each cycle. It defines:

- `sources` — Array of monitored sources, each with type, method, filtering rules,
  target domain, and value threshold.
- `scoring` — Provider chain for LLM-based value scoring with failover.
- `push` — Feishu Bot webhook config, hybrid cadence settings, deduplication rules.
- `state` — Path to the persistent state file.

## Workflow: Main Loop

### 1. Initialize

```
1. Read raw/watchlist/rules.yaml
2. Load or create watchlist_state.json from state.location
3. Determine current cycle: which sources are due for checking?
4. Connect to Feishu Bot webhook (validate webhook URL responds)
```

### 2. Fetch Phase (per source)

For each enabled source that is due (based on `last_checked` + `poll_interval_sec`):

#### Source Type: `hackernews` (method: `stream`)

```
1. GET {endpoint}/v0/updates.json → returns {items: [...], profiles: [...]}
2. For each changed story ID, GET {endpoint}/v0/item/{id}.json
3. Filter: title matches keywords (case-insensitive), score ≥ min_score
4. Deduplicate against state.seen_items (by HN item ID)
5. Limit to max_items_per_cycle
6. For each matching item: create content record {title, url, summary, source_name}
```

The `/v0/updates` endpoint is lightweight — it returns only changed item IDs and
profiles since the last request. This effectively provides event-driven behavior
without true streaming. Poll at `poll_interval_sec` (30s recommended).

#### Source Type: `rss` (method: `poll`)

```
1. GET {url} with headers:
   - If-None-Match: {etag from state for this source}
   - User-Agent: "Hermes-Watchlist/1.0"
2. If 304 Not Modified → skip (no new items)
3. Parse RSS/Atom XML → extract title, link, summary, pubDate for each item
4. Filter: title/summary matches keywords (if defined), pubDate after last_checked
5. Deduplicate against state.seen_items (by URL)
6. Limit to max_items_per_cycle
7. Save the ETag from the response header for next cycle
8. For each matching item: create content record
```

#### Source Type: `api` (method: `poll`)

```
1. Make API request per source endpoint specification:
   - HN Firebase: GET {endpoint}/v0/updates.json (handled separately as hackernews type)
   - GitHub Events: GET https://api.github.com/events with If-None-Match
   - FRED: GET https://api.stlouisfed.org/fred/series/updates?api_key={key}&...
2. Parse JSON response
3. Filter, deduplicate, limit per source config
4. Save ETag/last-modified for next cycle
5. Create content records
```

#### Source Type: `x_scrape` (method: `poll`, Playwright-based)

```
⚠️ This is the FREE alternative to X API v2. See cost comparison in ## Cost Analysis.

For each account in source.accounts:
  1. Navigate to https://x.com/{account} (remove @ prefix)
  2. Wait for timeline to load (3-5s after navigation)
  3. Extract the latest N posts (up to filter.max_items_per_account):
     - Post text
     - Post timestamp
     - Post URL (https://x.com/{account}/status/{id})
     - Any quoted/linked content
  4. Apply random delay between accounts (anti_detection.random_delay_ms)
  5. Create content record for each new post (deduplicate by tweet ID)
```

**Anti-detection measures** (see `wiki/finance/chance/` for detailed browser
fingerprinting background):

```
BEFORE each scraping session:
  - Set random viewport: pick from pool [{1920,1080}, {1440,900}, {1536,864},
    {2560,1440}, {1680,1050}]
  - Set random User-Agent: pick from pool of recent Chrome/Firefox/Safari UAs
  - Apply Canvas noise: inject JS to slightly perturb Canvas/WebGL rendering
    (important: X uses Canvas fingerprinting for bot detection)

DURING scraping:
  - Between account navigations: sleep random(2000, 8000) ms
  - Before extracting content: sleep random(1500, 4000) ms (simulate reading)
  - Scroll timeline slowly with random pauses
  - Use persistent browser profile (maintains login cookies)

AFTER scraping:
  - Close page but keep browser context warm for next cycle
  - If encountering login wall → use persistent profile with saved credentials
```

The anti-detection strategy is based on the browser fingerprinting knowledge
accumulated in:
- [[wiki/finance/chance/browser-fingerprinting-techniques_summary]]
- [[wiki/finance/chance/browser-fingerprinting-techniques-research-supplement_summary]]

Key insight: X's TLS fingerprinting (Client Hello analysis) is the hardest to
evade. Playwright's Chromium has a distinctive TLS fingerprint. If X starts
blocking based on TLS fingerprint, the only mitigation is switching to a
real-browser-based approach or using X API v2.

### 3. Scoring Phase (per content item)

For each content record collected in the fetch phase:

```
1. Build scoring prompt from scoring.prompt template:
   - Replace {domain} with source.target_domain
   - Replace {title}, {source_name}, {source_type}, {summary} with actual values
2. Try providers in scoring.provider_chain order:
   a. Check if provider is in circuit-breaker cooldown → skip
   b. Send request to provider's API
   c. If success → parse JSON {score, reason}, store result, break
   d. If HTTP 429 → record Retry-After, activate circuit breaker, try next
   e. If other error → try next provider
3. If ALL providers fail → mark item as "scoring_failed", include in next cycle
4. Update provider quota counters in state
```

**Provider API details:**

Google AI Studio:
```
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}
Headers: Content-Type: application/json
Body: {
  "contents": [{"parts": [{"text": "{scoring_prompt}"}]}],
  "generationConfig": {"temperature": 0, "maxOutputTokens": 128}
}
Rate limit headers: Check for 429 with Retry-After
```

OpenRouter:
```
POST https://openrouter.ai/api/v1/chat/completions
Headers: Authorization: Bearer {api_key}, Content-Type: application/json
Body: {
  "model": "{model}",
  "messages": [{"role": "user", "content": "{scoring_prompt}"}],
  "temperature": 0,
  "max_tokens": 128
}
```

### 4. Push Phase

After all items are scored, determine what to push:

#### Real-time Push (score ≥ push.realtime.min_score, typically 9)

For each item with score ≥ 9 that hasn't been pushed before:

```
POST {FEISHU_BOT_WEBHOOK_URL}
Headers: Content-Type: application/json
Body (post format):
{
  "msg_type": "post",
  "content": {
    "post": {
      "zh_cn": {
        "title": "🔥 高价值实时推送 (评分 {score}/10)",
        "content": [
          [{"tag": "text", "text": "来源: {source_name}"}],
          [{"tag": "text", "text": "领域: {target_domain}"}],
          [{"tag": "text", "text": "{summary}"}],
          [{"tag": "a", "text": "查看原文", "href": "{url}"}],
          [{"tag": "text", "text": "评分理由: {reason}"}]
        ]
      }
    }
  }
}
```

Limit: max realtime.max_per_day (10) per day.

#### Daily Digest (at push.daily_digest.time, typically 09:00 UTC+8)

Compile all items from the past 24 hours with score ≥ daily_digest.min_score (6)
that were NOT already pushed as real-time alerts (deduplication).

```
POST {FEISHU_BOT_WEBHOOK_URL}
Headers: Content-Type: application/json
Body (interactive card format):
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {"tag": "plain_text", "content": "📋 每日知识摘要 ({date})"},
      "template": "blue"
    },
    "elements": [
      {
        "tag": "div",
        "text": {"tag": "lark_md", "content": "今日共发现 {total_scored} 条内容，其中 {pushed_count} 条值得关注："}
      },
      ...item_rows,
      {
        "tag": "hr"
      },
      {
        "tag": "note",
        "elements": [
          {"tag": "plain_text", "content": "评分 ≥ 6 进入摘要 | ≥ 9 实时推送 | 回复任意内容链接可入库"}
        ]
      }
    ]
  }
}
```

Each item row:
```
{
  "tag": "div",
  "fields": [
    {"tag": "lark_md", "content": "**{score}/10** {title}"},
    {"tag": "lark_md", "content": "{source_name} | [{target_domain}]"}],
  "extra": {"tag": "lark_md", "content": "{reason}\n[查看原文]({url})"}
}
```

### 5. Persist State

After each cycle, save `watchlist_state.json`:

```json
{
  "version": 1,
  "updated": "2026-05-14T09:00:00+08:00",
  "sources": {
    "hackernews-ai": {
      "last_checked": "2026-05-14T08:55:00+08:00",
      "last_item_id": 12345678,
      "etag": null
    },
    "arxiv-cs-ai": {
      "last_checked": "2026-05-14T08:00:00+08:00",
      "etag": "\"abc123\""
    }
  },
  "seen_items": {
    "hn://12345678": "2026-05-14T08:55:00+08:00",
    "arxiv://2505.12345": "2026-05-14T08:00:00+08:00",
    "x://tweet/1920456789012345678": "2026-05-14T08:30:00+08:00"
  },
  "circuit_breakers": {
    "openrouter:meta-llama/llama-4-maverick:free": {
      "cooldown_until": "2026-05-14T09:05:00+08:00",
      "consecutive_failures": 2
    }
  },
  "quota_counters": {
    "google_ai_studio:gemini-2.5-flash-lite": {
      "requests_today": 42,
      "date": "2026-05-14"
    }
  },
  "push_log": {
    "daily_digest_last_sent": "2026-05-14T09:00:00+08:00",
    "realtime_today": 3,
    "realtime_date": "2026-05-14"
  }
}
```

Clean up seen_items older than push.deduplication.seen_ttl_hours (168h = 7 days).

## Scheduling

Hermes should run the main loop on this schedule:

| Cycle | When | What |
|-------|------|------|
| **Fast cycle** | Every 30s | Check HN `/v0/updates` (stream sources) |
| **Normal cycle** | Every 5 min | Check Jin10 RSS, GitHub Events |
| **Slow cycle** | Every 30 min | Check X/Twitter accounts (x_scrape) |
| **Hourly cycle** | Every 60 min | Check arXiv, AI blogs, 36Kr, Huxiu |
| **Daily digest** | 09:00 UTC+8 | Compile and send daily digest card |
| **Daily cycle** | Every 24h | Check FRED economic data |

Implementation approach:
- Use a simple event loop with `asyncio.sleep()`.
- Track next check time per source. On each loop iteration, check which sources
  are due.
- The daily digest is triggered by wall-clock time, not interval.

## X/Twitter Scraping Setup (Cost Analysis)

### Cost Comparison: X API v2 vs Playwright Scraping

| Approach | Monthly Cost | Latency | Reliability | Maintenance |
|----------|-------------|---------|-------------|-------------|
| X API v2 (20 accounts, 48x/day) | ~$720/month ($24/day) | Low (API) | High (SLA) | Low |
| Playwright scraping | ~$0 (existing infra) | Medium (browser) | Medium (anti-bot risk) | Medium (UA rotation, fingerprint updates) |

**Recommendation**: Start with Playwright scraping (free). Only switch to X API v2
if X consistently blocks the scraper and maintenance cost exceeds API cost.

### Playwright Persistent Profile Setup

```
1. Launch persistent context:
   const context = await chromium.launchPersistentContext(
     userDataDir,  // e.g., ~/.hermes/playwright-profile
     { headless: true }
   );

2. Ensure X login cookies are present:
   - Manual one-time login: navigate to x.com/login, sign in
   - The cookies persist in userDataDir

3. Verify: navigate to x.com → should show logged-in timeline
```

### Anti-Detection Implementation

```
// Random viewport
const viewports = [
  {width: 1920, height: 1080},
  {width: 1440, height: 900},
  {width: 1536, height: 864},
  {width: 2560, height: 1440},
  {width: 1680, height: 1050},
];
const vp = viewports[Math.floor(Math.random() * viewports.length)];
await page.setViewportSize(vp);

// Random User-Agent
const userAgents = [
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  // ... more UAs from pool
];

// Canvas noise injection
await page.addInitScript(() => {
  const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toDataURL = function(...args) {
    const ctx = this.getContext('2d');
    if (ctx) {
      // Add subtle noise to a random pixel
      const x = Math.floor(Math.random() * this.width);
      const y = Math.floor(Math.random() * this.height);
      const imgData = ctx.getImageData(x, y, 1, 1);
      imgData.data[0] ^= 1;  // Flip one bit in red channel
      ctx.putImageData(imgData, x, y);
    }
    return originalToDataURL.apply(this, args);
  };
});

// Random delay helper
const randomDelay = () => new Promise(r =>
  setTimeout(r, 2000 + Math.random() * 6000)
);
```

## Manual Ingest Integration

After the user receives a push notification and wants to save content to the
knowledge base:

1. User replies to the Feishu bot message or sends the content URL to Hermes.
2. Hermes triggers the standard **Clip** workflow (if URL) or creates a raw file
   from the content.
3. Hermes triggers the standard **Ingest** workflow against the new raw source.

The watchlist system does NOT auto-ingest. All ingest requires explicit user
confirmation. This preserves the manual verification step in the knowledge base
workflow.

## Error Handling

| Error | Handling |
|-------|----------|
| rules.yaml not found | Log error, skip cycle, notify admin (once) |
| Feishu webhook unreachable | Log error, retry with exponential backoff (max 3 retries) |
| All scoring providers exhausted | Queue items for next cycle, include note in next digest |
| X scraping blocked | Log warning, try with fresh profile, notify if persistent |
| RSS feed returns 5xx | Skip this cycle, retry next cycle |
| state.json corrupted | Reset from scratch, log warning |
| Playwright browser crash | Restart browser context, retry failed accounts |

## References

- [[wiki/watchlist/index]] — Watchlist domain overview.
- [[wiki/llm/free-models/index]] — Free model pool and failover chain design.
- [[wiki/finance/chance/browser-fingerprinting-techniques_summary]] — Browser
  fingerprinting techniques for X scraping anti-detection.
- `raw/watchlist/rules.yaml` — Source of truth for all configuration.

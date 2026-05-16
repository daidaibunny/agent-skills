---
name: opencli
description: Universal internet access via OpenCLI. Use opencli as the PRIMARY method for ALL web content retrieval — Twitter/X, Reddit, HackerNews, Bloomberg, Xueqiu, Bilibili, Zhihu, Substack, CoinGecko, and 100+ more sites. Replaces Playwright scraping, direct HTTP calls, and RSS parsing for any site that OpenCLI supports. See SOURCE_REGISTRY for the complete list. Use when an agent needs to access any web content.
---

# OpenCLI — Universal Internet Access

OpenCLI is the **primary interface for all web content retrieval** in this knowledge
base. It transforms 100+ websites into deterministic CLI commands with JSON output,
reusing the user's logged-in Chrome session through a lightweight browser bridge.

**No token cost. No anti-detection headaches. One interface for everything.**

## Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  opencli CLI  │────▶│  Daemon (:19825) │────▶│  Chrome Ext   │
│  (npm global) │     │  (local process) │     │  (browser)    │
└──────────────┘     └─────────────────┘     └──────────────┘
                            │
                    ┌───────┴───────┐
                    │  Public API   │  ← no browser needed
                    │  Adapters     │
                    └───────────────┘
```

## Location

```text
/Users/lyw/Desktop/knowledge-base
```

Repository submodule:

```text
opencli/   # git submodule → https://github.com/jackwener/opencli
```

Keep the submodule updated:

```bash
cd opencli && git pull --ff-only origin main
```

## Required Setup

### 1. Install OpenCLI CLI

```bash
npm install -g @jackwener/opencli
```

### 2. Install Chrome Extension

Install **OpenCLI** from [Chrome Web Store](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk).

### 3. Verify

```bash
opencli doctor
```

Should show:
```
[OK] Daemon: running on port 19825
[OK] Extension: connected
```
### 4. Profile Management

```bash
opencli profile list          # list connected Chrome profiles
opencli profile use <ctxId>   # set default profile
```

Use `--profile <ctxId>` to target a specific profile:
```bash
opencli --profile udmzuh2k twitter tweets @user -f json
```

## Usage Pattern

### For Agents

**ALWAYS prefer opencli over any other method** (Playwright, direct HTTP, RSS parsing)
when the target site is in the SOURCE_REGISTRY below.

Standard invocation:

```bash
opencli --profile udmzuh2k <site> <command> [args] -f json
```

Examples:

```bash
# Twitter/X
opencli --profile udmzuh2k twitter tweets @Michael_Liu93 --limit 5 -f json

# HackerNews
opencli --profile udmzuh2k hackernews top --limit 10 -f json

# Reddit
opencli --profile udmzuh2k reddit hot --limit 10 -f json

# Bloomberg (RSS, no auth)
opencli --profile udmzuh2k bloomberg markets --limit 10 -f json

# Xueqiu (雪球)
opencli --profile udmzuh2k xueqiu hot-stock -f json

# Sina Finance (新浪财经)
opencli --profile udmzuh2k sinafinance rolling-news -f json

# 36Kr
opencli --profile udmzuh2k 36kr hot --limit 10 -f json

# CoinGecko
opencli --profile udmzuh2k coingecko trending -f json

# Bilibili
opencli --profile udmzuh2k bilibili hot --limit 10 -f json

# StackOverflow
opencli --profile udmzuh2k stackoverflow hot -f json

# DevTo
opencli --profile udmzuh2k devto top -f json

# Yahoo Finance
opencli --profile udmzuh2k yahoo-finance quote TSLA -f json

# Substack
opencli --profile udmzuh2k substack feed -f json
```

**Output format**: Always use `-f json` for machine-readable output. Also available:
`table`, `plain`, `yaml`, `md`, `csv`.

### When opencli is NOT available

If the target site is NOT in the SOURCE_REGISTRY, fall back to:
1. Direct HTTP + requests (for public APIs)
2. Playwright (for sites requiring browser interaction, using the Clip skill's anti-detection)

---

## SOURCE_REGISTRY

### 🔓 Public (no browser/auth needed — works anywhere)

| Site | Commands | Notes |
|------|----------|-------|
| `hackernews` | `top`, `new`, `best`, `ask`, `show`, `jobs`, `search`, `user` | Firebase API |
| `36kr` | `hot`, `news`, `search`, `article` | RSS + public API |
| `bloomberg` | `markets`, `economics`, `tech`, `main`, `politics`, `opinions`, `industries`, `businessweek`, `feeds`, `news <url>` | RSS feeds (no auth); `news` needs article URL |
| `stackoverflow` | `hot`, `search`, `bounties`, `unanswered`, `tag`, `user`, `read`, `related` | Stack Exchange API |
| `devto` | `top`, `tag`, `user` | Dev.to API |
| `sinafinance` | `news`, `rolling-news`, `stock`, `stock-rank` | Public + partial browser |
| `bluesky` | `trending`, `search`, `profile`, `user`, `feeds`, `thread` | Public API |
| `coingecko` | `top`, `coin`, `trending`, `exchanges`, `categories`, `global` | Public API |
| `yahoo-finance` | `quote` | Public API |
| `binance` | `price`, `prices`, `ticker`, `pairs`, `trades`, `depth`, `top`, `gainers`, `losers` | Public API |
| `arxiv` | `search`, `paper` | Public API (rate-limited: ~1 req/sec) |
| `producthunt` | `posts`, `today`, `hot`, `browse` | Public |
| `toutiao` | `articles`, `hot` | Public + partial browser |
| `barchart` | `quote`, `options`, `greeks`, `flow` | Public API |
| `eastmoney` | `hot-rank` | Public (东方财富) |
| `weibo` | `hot`, `search` | Public hot search |
| `wikipedia` | `search`, `summary`, `random`, `trending` | Public API |
| `github` | Trending (via plugin) | Public |
| `steam` | `top-sellers` | Public |
| `npm` | `search`, `package`, `downloads` | Public |
| `pypi` | `package`, `downloads` | Public |
| `mdn` | `search` | Public |
| `rfc` | `rfc` | Public |
| `dblp` | `search`, `author`, `paper`, `venue` | Public (CS bibliography) |
| `pubmed` | `search`, `article` | Public |
| `openreview` | `search`, `paper`, `reviews` | Public |
| `openalex` | `search`, `work` | Public |
| `endoflife` | `product` | Public |
| `defillama` | `protocols`, `protocol` | Public |
| `lesswrong` | `curated`, `frontpage`, `new`, `top`, `read`, `user` | Public |
| `lobsters` | `hot`, `newest`, `active`, `tag`, `read` | Public |

### 🔐 Browser (requires Chrome + logged-in session)

| Site | Commands | Auth Setup |
|------|----------|------------|
| `twitter` | `tweets`, `trending`, `search`, `timeline`, `profile`, `bookmarks`, `post`, `reply`, `like`, `follow`, `thread`, `download`, `notifications` | **Login required**. Go to `x.com` in Chrome and sign in. Verify with: `opencli twitter profile -f json` |
| `reddit` | `hot`, `frontpage`, `popular`, `search`, `subreddit`, `read`, `user`, `upvote`, `save`, `comment` | **Login recommended**. Works partially without login, full features require login at `reddit.com` |
| `xueqiu` | `hot-stock`, `feed`, `hot`, `search`, `stock`, `comments`, `watchlist`, `fund-holdings` | **Login required**. Go to `xueqiu.com` in Chrome and sign in (phone/WeChat). Verify: `opencli xueqiu feed -f json` |
| `bilibili` | `hot`, `search`, `history`, `feed`, `ranking`, `download`, `comments` | **Login recommended**. Basic features work without login. Full features require login at `bilibili.com` |
| `zhihu` | `hot`, `recommend`, `search`, `question`, `answer`, `follow`, `like`, `comment` | **Login required**. Go to `zhihu.com` in Chrome and sign in. |
| `linkedin` | `search`, `timeline` | **Login required**. Go to `linkedin.com` in Chrome and sign in. |
| `tiktok` | `explore`, `search`, `profile`, `user`, `following`, `like`, `comment` | **Login recommended**. Explore works without login. |
| `youtube` | `search`, `video`, `transcript`, `comments`, `channel`, `playlist`, `feed`, `history`, `subscriptions` | **Login recommended**. Search works without login. |
| `substack` | `feed`, `search`, `publication` | **Login recommended** for personalized feed. Public feed works without login. |
| `instagram` | `explore`, `profile`, `search`, `user`, `follow`, `like`, `comment`, `saved` | **Login required**. Go to `instagram.com` and sign in. |
| `facebook` | `feed`, `profile`, `search`, `friends`, `groups`, `events` | **Login required**. |
| `weixin` | `search`, `download`, `drafts`, `create-draft` | **Login required**. WeChat Official Account platform. |
| `boss` | `search`, `detail`, `recommend`, `joblist`, `greet`, `chatlist` | **Login required** (Boss直聘). |
| `nowcoder` | `hot`, `trending`, `topics`, `jobs`, `search`, `companies` | **Login recommended** (牛客网). |
| `douban` | `search`, `top250`, `subject`, `photos`, `download`, `marks`, `reviews` | **Login recommended** (豆瓣). |
| `weread` | `shelf`, `search`, `book`, `ranking`, `notebooks`, `highlights`, `notes` | **Login required** (微信读书). |
| `jike` | `feed`, `search`, `post`, `topic`, `user`, `comment`, `like`, `notifications` | **Login required** (即刻). |
| `pixiv` | `ranking`, `search`, `user`, `illusts`, `detail`, `download` | **Login required**. |
| `medium` | `feed`, `search`, `user` | **Login required**. |
| `spotify` | `auth`, `status`, `play`, `pause`, `search`, `queue` | **OAuth required**. Run `opencli spotify auth` first. |
| `eastmoney` | `hot-rank` | **Login required** (东方财富). Go to `eastmoney.com` and sign in. |
| `ths` | `hot-rank` | **Login required** (同花顺). |
| `tdx` | `hot-rank` | **Login required** (通达信). |
| `dianping` | `search`, `shop` | **Login required** (大众点评). |
| `maimai` | `search-talents` | **Login required** (脉脉). |
| `douyin` | `profile`, `videos`, `user-videos`, `stats`, `publish` | **Login required** (抖音). |
| `linux-do` | `feed`, `search`, `categories`, `tags`, `topic` | **Login required**. |

### 🔑 Other Auth

| Site | Auth Type | Setup |
|------|-----------|-------|
| `xiaoyuzhou` | Local credentials | Create `~/.opencli/xiaoyuzhou.json` |
| `spotify` | OAuth | `opencli spotify auth` |
| `ones` | ONES_BASE_URL env | Set `ONES_BASE_URL` env var |

---

## Login Setup Workflow

When a source requires login and the session is missing or expired:

### 1. DETECT — Run the command and check for auth failure

```bash
opencli --profile udmzuh2k <site> <command> -f json
```

Auth failure signals:
- Empty array `[]` for auth-required commands
- Error message containing "login", "auth", "unauthorized", "请登录"
- Status codes indicating redirect to login page

### 2. ABORT — Do NOT retry. Report to the user.

```
⚠️ [site] requires login. Current session appears to be missing or expired.

To fix:
1. Open Chrome and navigate to [site URL]
2. Sign in with your credentials
3. Verify with: opencli --profile udmzuh2k [site] [test-command] -f json

Once logged in, retry the operation.
```

### 3. VERIFY — After user confirms login

```bash
opencli --profile udmzuh2k <site> <test-command> -f json
```

### Tracked Login Status

| Site | Status | Last Verified | Notes |
|------|--------|---------------|-------|
| `twitter` | ✅ Logged in | 2026-05-16 | Full access |
| `xueqiu` | ✅ Logged in | 2026-05-16 | Full access |
| `linkedin` | ✅ Logged in | 2026-05-16 | Timeline works |
| `tiktok` | ✅ Partial | 2026-05-16 | Explore works without login |
| `weixin` | ✅ Partial | 2026-05-16 | Search works |
| `youtube` | ✅ Public | 2026-05-16 | Search works |
| `substack` | ✅ Public | 2026-05-16 | Feed works |
| `medium` | ✅ Public | 2026-05-16 | Feed works |
| `zhihu` | ❌ Not logged in | 2026-05-16 | Returns empty array |
| `eastmoney` | ❌ Not logged in | 2026-05-16 | Timeout |
| `jike` | ❌ Not logged in | 2026-05-16 | Returns empty array |
| `instagram` | ❌ Not logged in | 2026-05-16 | UNKNOWN error |
| `weread` | ❌ Not logged in | 2026-05-16 | AUTH_REQUIRED |
| `boss` | ❌ Not logged in | 2026-05-16 | AUTH_REQUIRED |
| `pixiv` | ❓ Unknown | - | Not tested |
| `facebook` | ❓ Unknown | - | Not tested |
| `spotify` | ❓ Not configured | - | OAuth setup needed |

---

## Integration With Watchlist

The watchlist runner should use `opencli` for all supported sources instead of
custom HTTP/Playwright code:

### Before (current)

```python
def fetch_x_scrape(source, state):
    # Custom Playwright subprocess with cookies
    subprocess.run(["node", "x_scraper.js", ...])
```

### After (target)

```python
def fetch_opencli(source, state):
    cmd = ["opencli", "--profile", source["profile"], source["site"], source["command"]]
    result = subprocess.run(cmd + ["-f", "json"], capture_output=True, text=True)
    items = json.loads(result.stdout)
```

### Source mapping in rules.yaml

```yaml
sources:
  - id: twitter-curated
    type: opencli
    site: twitter
    command: tweets
    profile: udmzuh2k
    accounts: ["@Michael_Liu93", "@ShanghaoJin", "@gemchange_ltd"]
    
  - id: reddit-hot
    type: opencli
    site: reddit
    command: hot
    profile: udmzuh2k
    
  - id: hackernews-top
    type: opencli
    site: hackernews
    command: top
    # public — no profile needed
```

---

## Server (Hermes) Setup

For remote access (Hermes server without Chrome):

```bash
# 1. Install Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update && sudo apt install -y google-chrome-stable

# 2. Install OpenCLI
npm install -g @jackwener/opencli

# 3. Install Chrome Extension (manual)
# Download from https://github.com/jackwener/opencli/releases
# Load unpacked extension in chrome://extensions

# 4. Start Chrome with remote debugging
google-chrome-stable --headless --remote-debugging-port=9222 --no-sandbox &

# 5. Verify
opencli doctor
```

⚠️ **Memory warning**: Chrome + daemon on the Hermes server (1.9GB RAM) will be tight.
Monitor memory usage. If OOM, run Chrome in `--headless` mode without GPU and limit
its memory.

---

## Agent Protocol

### ALL agents MUST follow this rule:

> **For ANY web content retrieval, check SOURCE_REGISTRY first. If the site is listed, use `opencli`. Only fall back to Playwright/direct HTTP if the site is NOT in the registry.**

### When a site requires login and has no active session:

1. **ABORT immediately** — do not retry, do not try alternative methods
2. **Report** to the user with the exact auth setup instructions from the SOURCE_REGISTRY
3. **Wait** for user confirmation before retrying

### When writing adapters or skills that access the web:

Always include both paths:
1. **Primary**: `opencli <site> <command> -f json`
2. **Fallback**: Playwright or direct HTTP (only for sites not in registry)

### When the OpenCLI submodule is outdated:

```bash
cd opencli && git pull --ff-only origin main
```

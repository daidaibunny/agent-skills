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
opencli profile list          # list connected profiles
opencli profile use <ctxId>   # set default (local: udmzuh2k, server: dwq6qaxw)
```

Use `--profile <ctxId>` per-command. Without it, `opencli` uses the default.
Public API commands (HN, StackOverflow, CoinGecko, etc.) ignore the profile and
work identically on both local and server.

## Usage Pattern

### For Agents

**ALWAYS prefer opencli over any other method** (Playwright, direct HTTP, RSS parsing)
when the target site is in the SOURCE_REGISTRY below.

Universal pattern (works both local and server):

```bash
# Server agent (profile dwq6qaxw):
opencli --profile dwq6qaxw <site> <command> [args] -f json

# Local agent (profile udmzuh2k):
opencli --profile udmzuh2k <site> <command> [args] -f json

# Public API (no profile needed, works everywhere):
opencli <site> <command> [args] -f json
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

### 2. ABORT — Do NOT retry.

**Server agent**: Tell user to log in on their Mac Chrome, then offer to sync cookies.
**Local agent**: Tell user to log in on their Chrome (same machine), then retry.

```
⚠️ [site] login expired.
→ Server: "Log in on your Mac Chrome. I'll export and sync cookies."
→ Local: "Log in on Chrome, then tell me to retry."
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
| `zhihu` | ✅ Logged in | 2026-05-16 | Hot works |
| `jike` | ✅ Logged in | 2026-05-16 | Feed works |
| `eastmoney` | ❌ Timeout | 2026-05-16 | Adapter timeout |
| `instagram` | ❌ Not logged in | 2026-05-16 | UNKNOWN error |
| `weread` | ❌ Not logged in | 2026-05-16 | AUTH_REQUIRED |
| `boss` | ❌ Not logged in | 2026-05-16 | AUTH_REQUIRED |

### Location Detection

Agents must determine their location before using OpenCLI. The correct profile
and capabilities differ by environment.

```bash
# Server: hostname starts with 'ip-' AND chrome-opencli service exists
hostname | grep -q "^ip-" && systemctl --user is-active chrome-opencli 2>/dev/null && LOCATION="SERVER" || LOCATION="LOCAL"
```

### Location Rules

| Environment | Profile | Capabilities | Cookie source |
|-------------|---------|-------------|---------------|
| **Local (Mac)** | `--profile udmzuh2k` | All browser sources via real Chrome | `~/Library/Application Support/Google/Chrome/Default/Cookies` |
| **Server (Hermes)** | `--profile dwq6qaxw` | Public API + Xueqiu only. Twitter → Playwright `x_scraper.js` | User exports from Mac → agent injects |

**Server agents**: Always use `--profile dwq6qaxw`. For Twitter, use `x_scraper.js` (not `opencli twitter` — IP-bound sessions fail).
**Local agents**: Always use `--profile udmzuh2k`. Can export cookies for server sync.

### Usage Examples

Use the profile matching your location. Public API sources work without a profile:

```bash
# Public API (both locations)
opencli hackernews top --limit 10 -f json

# Browser sources — use correct profile
opencli --profile dwq6qaxw xueqiu hot-stock -f json    # server
opencli --profile udmzuh2k twitter tweets @user -f json  # local only
```

## Cookie Management

Browser sources need login cookies in the server Chrome SQLite database
(`~/.config/google-chrome-opencli/Default/Cookies`). When cookies expire:

1. **ABORT immediately.** Do not retry.
2. Tell user: `⚠️ [site] login expired. Log in on Chrome → tell me → I sync.`
3. After user confirms: export from local Chrome SQLite → scp to server → inject into server Chrome SQLite → `systemctl --user restart chrome-opencli`.
4. Retry.

**Export (macOS)**:
```bash
python3 -c "import sqlite3,json,shutil;shutil.copy2('$HOME/Library/Application Support/Google/Chrome/Default/Cookies','/tmp/c.db');conn=sqlite3.connect('/tmp/c.db');rows=conn.execute('SELECT host_key,name,value,path,is_secure,is_httponly,expires_utc FROM cookies WHERE host_key LIKE ?',('%xueqiu.com%',)).fetchall();json.dump([{'name':r[1],'value':r[2],'domain':r[0],'path':r[3],'secure':bool(r[4]),'httpOnly':bool(r[5]),'expires':r[6]/1000000-11644473600 if r[6] else -1} for r in rows],open('/tmp/cookies.json','w'));print(f'{len(rows)} cookies')"
```

**Import (server)**:
```bash
systemctl --user stop chrome-opencli
python3 -c "
import sqlite3,json,time;d=json.load(open('/tmp/cookies.json'));db='$HOME/.config/google-chrome-opencli/Default/Cookies';c=sqlite3.connect(db);n=int((time.time()+11644473600)*1e6)
for x in d:
 e=int((x['expires']+11644473600)*1e6) if x['expires']>0 else 0;h=1 if x['expires']>0 else 0
 c.execute('INSERT OR REPLACE INTO cookies VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(n,x['domain'],'',x['name'],x['value'],b'',x.get('path','/'),e,x.get('secure',0),x.get('httpOnly',0),n,h,h,1,-1,2 if x.get('secure') else 0,443 if x.get('secure') else 80,n,0,0))
c.commit();c.close()
"
systemctl --user start chrome-opencli
```

**Twitter/X**: IP-bound sessions. Do NOT use `opencli twitter` on server. Use Playwright `x_scraper.js` at `~/.hermes/scripts/` which has its own profile with consistent server-IP cookies.

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
    profile: dwq6qaxw         # server profile (change to udmzuh2k for local)
    accounts: ["@Michael_Liu93", "@ShanghaoJin"]
    
  - id: hackernews-top
    type: opencli
    site: hackernews
    command: top
    # public — no profile needed, works both local and server
```

---

## Server (Hermes) Setup

### Architecture Decision

After testing, the pragmatic architecture is:

- **Server (Hermes)**: OpenCLI for **public API adapters only** (no Chrome needed). These work without any browser: hackernews, reddit, stackoverflow, coingecko, bloomberg (RSS), devto, bluesky, producthunt, etc.
- **Local machine**: OpenCLI for **all sources** including browser-auth ones (Twitter, Xueqiu, Zhihu, Jike, etc.)
- **X/Twitter on server**: Keep using Playwright `x_scraper.js` (already working, already has cookies)

**Why not Chrome on server?**
- Server has 1.9GB RAM. Chrome + Playwright Chromium + Hermes + Docker stack = OOM.
- Headless Chrome doesn't support extensions properly.
- Public API adapters don't need Chrome at all.

### Server Installation (public API only)

```bash
npm install -g @jackwener/opencli
opencli hackernews top --limit 1 -f json  # verify
```

No Chrome needed. The daemon auto-starts when `opencli` is called.

### Local Installation (full)

```bash
npm install -g @jackwener/opencli
# Install Chrome Extension from Chrome Web Store
opencli doctor  # verify extension connected
```

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

#!/usr/bin/env python3
"""
Watchlist Runner v2 — no_agent cron script for Hermes.

Reads raw/watchlist/rules.yaml, fetches new content, scores via provider chain,
pushes via Feishu Bot. Session-stealth defaults: ETag, rotating UA pool, delays.
"""

from __future__ import annotations

import hashlib, json, os, re, signal, subprocess, sys, time, uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import feedparser, requests, yaml

# Load Hermes .env so no_agent cron subprocess has access to API keys
_DOTENV_PATH = Path(os.path.expanduser("~/.hermes/.env"))
if _DOTENV_PATH.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(str(_DOTENV_PATH), override=True)
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KB_PATH = Path(os.path.expanduser("~/knowledge-base"))
RULES_PATH = KB_PATH / "raw" / "watchlist" / "rules.yaml"
STATE_PATH = Path(os.path.expanduser("~/.hermes/cron/output/watchlist_state.json"))
TZ_UTC8 = timezone(timedelta(hours=8))
SILENT = "[SILENT]"

# Global timeout: script must finish within this window
_DEADLINE_SEC = 180  # cron runs every 5 min, first run with no state may need time

_UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
]
_REQ_TIMEOUT = 12


def now_iso() -> str:
    return datetime.now(TZ_UTC8).isoformat()


def today_str() -> str:
    return datetime.now(TZ_UTC8).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            s = json.loads(STATE_PATH.read_text())
            s.setdefault("sources", {})
            s.setdefault("seen_items", {})
            s.setdefault("push_log", {})
            return s
        except Exception:
            pass
    return {"version": 1, "sources": {}, "seen_items": {}, "push_log": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def http_get(url: str, etag: str | None = None) -> Tuple[int, str, str | None]:
    ua = _UA_POOL[hash(url) % len(_UA_POOL)]  # stable per-url UA
    h = {"User-Agent": ua, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"}
    if etag:
        h["If-None-Match"] = etag
    try:
        r = requests.get(url, headers=h, timeout=_REQ_TIMEOUT)
        new_etag = r.headers.get("ETag", "").strip('"') or None
        return r.status_code, r.text, new_etag
    except Exception:
        return 0, "", None


def http_post(url: str, payload: dict, api_key: str = "") -> Tuple[int, str]:
    h = {"User-Agent": _UA_POOL[0], "Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    try:
        r = requests.post(url, json=payload, headers=h, timeout=15)
        return r.status_code, r.text
    except Exception:
        return 0, ""


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def fetch_hn(source: dict, state: dict) -> List[dict]:
    items = []
    fcfg = source.get("filter", {})
    keywords = [k.lower() for k in fcfg.get("keywords", [])]
    min_score = fcfg.get("min_score", 10)
    max_n = fcfg.get("max_items_per_cycle", 20)
    ep = source["endpoint"]

    st, body, _ = http_get(f"{ep}/v0/topstories.json")
    if st != 200:
        return items
    try:
        ids = json.loads(body)[:100]
    except Exception:
        return items

    seen = state.setdefault("seen_items", {})
    n = 0
    for sid in ids:
        if n >= max_n:
            break
        key = f"hn://{sid}"
        if key in seen:
            continue
        st, body, _ = http_get(f"{ep}/v0/item/{sid}.json")
        if st != 200:
            continue
        try:
            obj = json.loads(body)
        except Exception:
            continue
        title_l = (obj.get("title") or "").lower()
        sco = obj.get("score", 0)
        if sco < min_score:
            continue
        if keywords and not any(k in title_l for k in keywords):
            continue
        url = obj.get("url") or f"https://news.ycombinator.com/item?id={sid}"
        items.append(
            {
                "id": key,
                "title": obj.get("title", ""),
                "url": url,
                "summary": (obj.get("text") or "")[:400],
                "source_name": "Hacker News",
                "source_type": "hackernews",
            }
        )
        seen[key] = now_iso()
        n += 1
    return items


def fetch_rss(source: dict, state: dict) -> List[dict]:
    items = []
    sid = source["id"]
    fcfg = source.get("filter", {})
    keywords = [k.lower() for k in fcfg.get("keywords", [])]
    max_n = fcfg.get("max_items_per_cycle", 20)

    urls = source.get("urls", [source.get("url", "")])
    if isinstance(urls, str):
        urls = [urls]
    urls = [u for u in urls if u]

    src_st = state.setdefault("sources", {}).setdefault(sid, {})
    etag = src_st.get("etag")
    seen = state.setdefault("seen_items", {})

    for url in urls:
        st, body, new_etag = http_get(url, etag=etag)
        if st == 304:
            if new_etag:
                src_st["etag"] = new_etag
            continue
        if st != 200:
            continue
        if new_etag:
            src_st["etag"] = new_etag

        feed = feedparser.parse(body)
        n = 0
        for e in feed.entries:
            if n >= max_n:
                break
            title_l = (e.get("title") or "").lower()
            link = e.get("link", "")
            key = f"rss://{hashlib.md5(link.encode()).hexdigest()[:12]}"
            if key in seen:
                continue
            if keywords and not any(k in title_l for k in keywords):
                continue
            summ = re.sub(r"<[^>]+>", "", e.get("summary", e.get("description", "")))[
                :400
            ]
            items.append(
                {
                    "id": key,
                    "title": e.get("title", ""),
                    "url": link,
                    "summary": summ,
                    "source_name": source.get("description", sid),
                    "source_type": "rss",
                }
            )
            seen[key] = now_iso()
            n += 1
    return items


def fetch_wallstreetcn(source: dict, state: dict) -> List[dict]:
    """Fetch 华尔街见闻 7x24 flash news via REST API (no auth)."""
    items = []
    sid = source["id"]
    ep = source["endpoint"]
    params = source.get("params", {})
    fcfg = source.get("filter", {})
    max_n = fcfg.get("max_items_per_cycle", 30)

    src_st = state.setdefault("sources", {}).setdefault(sid, {})
    cursor = src_st.get("cursor")

    qs = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{ep}?{qs}"
    if cursor:
        url += f"&cursor={cursor}"
    else:
        url += "&first_page=true"

    st, body, _ = http_get(url)
    if st != 200:
        return items

    try:
        data = json.loads(body)
    except Exception:
        return items

    if data.get("code") != 20000:
        return items

    seen = state.setdefault("seen_items", {})
    live_items = data.get("data", {}).get("items", [])
    next_cursor = data.get("data", {}).get("next_cursor", "")

    n = 0
    for li in live_items:
        if n >= max_n:
            break
        live_id = str(li.get("id", ""))
        key = f"wscn://{live_id}"
        if key in seen:
            continue
        content = li.get("content_text", "")[:400]
        title = li.get("title", "") or content[:80]
        uri = li.get("uri", "")
        if uri and not uri.startswith("http"):
            uri = f"https://wallstreetcn.com/livenews/{live_id}"

        items.append(
            {
                "id": key,
                "title": title,
                "url": uri,
                "summary": content,
                "source_name": "华尔街见闻·7x24",
                "source_type": "wallstreetcn",
            }
        )
        seen[key] = now_iso()
        n += 1

    if next_cursor:
        src_st["cursor"] = next_cursor

    return items


def fetch_x_scrape(source: dict, state: dict, scripts_dir: Path) -> List[dict]:
    """Fetch recent tweets from X accounts via Playwright subprocess."""
    items = []
    sid = source["id"]
    accounts = source.get("accounts", [])
    fcfg = source.get("filter", {})
    max_per = fcfg.get("max_items_per_account", 5)

    if not accounts:
        return items

    scraper_js = scripts_dir / "x_scraper.js"
    if not scraper_js.exists():
        return items

    node_bin = os.path.expanduser("~/.hermes/node/bin/node")
    if not os.path.exists(node_bin):
        node_bin = "node"  # fallback to PATH

    try:
        result = subprocess.run(
            [node_bin, str(scraper_js)] + accounts,
            capture_output=True,
            text=True,
            timeout=120,
        )
        data = json.loads(result.stdout.strip() or "[]")
    except Exception:
        return items

    seen = state.setdefault("seen_items", {})

    for tw in data:
        if len(items) >= max_per * len(accounts):
            break
        tweet_id = tw.get("url", "").split("/")[-1] if tw.get("url") else ""
        key = f"x://{tweet_id}"
        if key in seen or not tweet_id:
            continue
        items.append(
            {
                "id": key,
                "title": tw.get("text", "")[:80],
                "url": tw.get("url", ""),
                "summary": tw.get("text", "")[:400],
                "source_name": f"X/{tw.get('account', '')}",
                "source_type": "x_scrape",
            }
        )
        seen[key] = now_iso()

    return items


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_items(items: List[dict], target_domain: str, rules: dict) -> None:
    scfg = rules.get("scoring", {})
    chain = scfg.get("provider_chain", [])
    tpl = scfg.get("prompt", "")
    if not chain:
        return

    scored = 0
    _MAX_SCORE = 15  # max items to score per cycle
    _SCORE_LIMIT_SEC = 140  # stop scoring after this many seconds for fetch+push

    score_start = time.time()

    for item in items:
        if scored >= _MAX_SCORE:
            break
        scored += 1
        prompt = tpl.replace("{domain}", target_domain)
        prompt = prompt.replace("{title}", item.get("title", ""))
        prompt = prompt.replace("{source_name}", item.get("source_name", ""))
        prompt = prompt.replace("{source_type}", item.get("source_type", ""))
        prompt = prompt.replace("{summary}", item.get("summary", ""))

        # Time-box scoring: if we are running out of time, stop scoring
        if time.time() - score_start > _SCORE_LIMIT_SEC:
            break

        for p in chain:
            # Each provider tries primary key first, fallback key only on 429
            key_env = p.get("api_key_env", "")
            keys = [
                k
                for k in [
                    os.getenv(key_env, ""),
                    os.getenv(p.get("api_key_fallback_env", ""), ""),
                ]
                if k
            ]
            if not keys:
                continue
            for cur_key in keys:
                try:
                    if p["provider"] == "google_ai_studio":
                        sco, reason = _score_google(prompt, p, cur_key)
                    else:
                        sco, reason = _score_openrouter(prompt, p, cur_key)
                    if sco > 0:
                        item["score"] = sco
                        item["reason"] = reason
                        break
                except Exception:
                    continue
            if item.get("score", 0) > 0:
                break
        item.setdefault("score", 0)


def _score_google(prompt: str, p: dict, api_key: str) -> Tuple[int, str]:
    url = f"{p['base_url']}/models/{p['model']}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 128},
    }
    st, body = http_post(url, payload)
    if st != 200:
        return 0, ""
    try:
        text = json.loads(body)["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return 0, ""
    return _parse(text)


def _score_openrouter(prompt: str, p: dict, api_key: str) -> Tuple[int, str]:
    url = f"{p['base_url']}/chat/completions"
    # Check for rate limits
    st, body = http_post(
        url,
        {
            "model": p["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 128,
        },
        api_key=api_key,
    )
    if st == 429:
        return 0, "rate_limited"
    if st != 200:
        return 0, ""
    try:
        text = json.loads(body)["choices"][0]["message"]["content"]
    except Exception:
        return 0, ""
    return _parse(text)


def _parse(text: str) -> Tuple[int, str]:
    try:
        d = json.loads(text.strip())
        return max(0, min(10, int(d.get("score", 0)))), str(d.get("reason", ""))
    except Exception:
        m = re.search(r"\{[^}]+\}", text)
        if m:
            try:
                d = json.loads(m.group())
                return max(0, min(10, int(d.get("score", 0)))), str(d.get("reason", ""))
            except Exception:
                pass
    return 0, ""


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------


def _webhook_url(rules: dict) -> str:
    return os.getenv(rules.get("push", {}).get("webhook_env", ""), "")


def push_realtime(items: List[dict], rules: dict) -> int:
    wh = _webhook_url(rules)
    if not wh:
        print("[watchlist] WARNING: Feishu webhook not configured", file=sys.stderr)
        return 0
    threshold = rules.get("push", {}).get("realtime", {}).get("min_score", 9)
    high = [it for it in items if it.get("score", 0) >= threshold]
    pushed = 0
    for it in high[:10]:
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"\U0001f525 {it['score']}/10 | {it.get('target_domain', '')}",
                        "content": [
                            [{"tag": "text", "text": it.get("title", "")}],
                            [
                                {
                                    "tag": "text",
                                    "text": f"{it.get('source_name', '')} — {it.get('reason', '')}",
                                }
                            ],
                            [
                                {
                                    "tag": "a",
                                    "text": "\u67e5\u770b\u539f\u6587",
                                    "href": it.get("url", ""),
                                }
                            ],
                        ],
                    }
                }
            },
        }
        st, _ = http_post(wh, payload)
        if st == 200:
            it["realtime_pushed"] = True
            pushed += 1
        time.sleep(0.3)
    return pushed


def push_digest(items: List[dict], rules: dict, state: dict) -> bool:
    wh = _webhook_url(rules)
    if not wh:
        return False
    plog = state.setdefault("push_log", {})
    if plog.get("daily_digest_last_sent") == today_str():
        return False

    min_s = rules.get("push", {}).get("daily_digest", {}).get("min_score", 6)
    digest = [
        it
        for it in items
        if it.get("score", 0) >= min_s and not it.get("realtime_pushed")
    ]
    if not digest:
        return False

    digest.sort(key=lambda x: -x.get("score", 0))
    dstr = datetime.now(TZ_UTC8).strftime("%Y\u5e74%m\u6708%d\u65e5")
    total = len(items)

    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"\u4eca\u65e5\u53d1\u73b0 **{total}** \u6761\u5185\u5bb9\uff0c\u5176\u4e2d **{len(digest)}** \u6761\u503c\u5f97\u5173\u6ce8\uff1a",
            },
        },
        {"tag": "hr"},
    ]

    for it in digest[:15]:
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{it['score']}/10** [{it.get('target_domain', '')}] {it.get('title', '')}\n"
                        f"{it.get('source_name', '')} | {it.get('reason', '')}\n"
                        f"[\u67e5\u770b\u539f\u6587]({it.get('url', '')})"
                    ),
                },
            }
        )
        elements.append({"tag": "hr"})

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"\U0001f4cb \u6bcf\u65e5\u77e5\u8bc6\u6458\u8981 ({dstr})",
                },
                "template": "blue",
            },
            "elements": elements,
        },
    }
    st, _ = http_post(wh, payload)
    if st == 200:
        plog["daily_digest_last_sent"] = today_str()
        return True
    return False


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


def archive_items(items: list, kb_path: Path, state: dict) -> None:
    """Write daily digest markdown and queue high-score items for ingest."""
    date_str = today_str()
    digest_dir = kb_path / "raw" / "daily-digest"
    digest_dir.mkdir(parents=True, exist_ok=True)

    # Daily digest markdown
    scored_items = [it for it in items if it.get("score", 0) >= 6]
    if scored_items:
        scored_items.sort(key=lambda x: -x.get("score", 0))
        lines = [
            f"# Daily Digest — {date_str}",
            "",
            f"**{len(scored_items)} items** scored ≥ 6 out of {len(items)} fetched.",
            "",
            "| # | Score | Domain | Title | Source |",
            "|---|-------|--------|-------|--------|",
        ]
        for i, it in enumerate(scored_items, 1):
            title = it.get("title", "")[:60]
            url = it.get("url", "")
            title_link = f"[{title}]({url})" if url else title
            lines.append(
                f"| {i} | **{it['score']}** | {it.get('target_domain', '')} | "
                f"{title_link} | {it.get('source_name', '')} |"
            )
        lines.append("")
        lines.append(f"*Generated: {now_iso()}*")
        (digest_dir / f"{date_str}.md").write_text("\n".join(lines))

    # Queue high-score items (≥8) for auto-ingest — save raw files + manifest
    ingest_candidates = [it for it in items if it.get("score", 0) >= 8]
    if ingest_candidates:
        manifest_path = digest_dir / "ingest-manifest.json"
        manifest = []
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception:
                pass

        for it in ingest_candidates:
            domain = it.get("target_domain", "unknown")
            raw_dir = kb_path / "raw" / domain
            raw_dir.mkdir(parents=True, exist_ok=True)

            # Clean title for filename
            safe_title = re.sub(r"[^\w\s-]", "", it.get("title", "untitled"))[
                :50
            ].strip()
            safe_title = re.sub(r"[-\s]+", "-", safe_title).strip("-") or "untitled"
            slug = safe_title.lower()[:60]

            # Avoid overwriting existing files
            raw_path = raw_dir / f"{slug}.md"
            if not raw_path.exists():
                raw_content = (
                    f"# {it.get('title', 'Untitled')}\n\n"
                    f"**Source**: {it.get('source_name', '')}\n"
                    f"**URL**: {it.get('url', '')}\n"
                    f"**Score**: {it['score']}/10\n"
                    f"**Date**: {date_str}\n\n"
                    f"**Why**: {it.get('reason', '')}\n\n"
                    f"## Summary\n\n"
                    f"{it.get('summary', 'No summary available.')}\n"
                )
                raw_path.write_text(raw_content)

            manifest.append(
                {
                    "raw_path": str(raw_path),
                    "domain": domain,
                    "title": it.get("title", ""),
                    "url": it.get("url", ""),
                    "score": it.get("score", 0),
                    "reason": it.get("reason", ""),
                    "source_name": it.get("source_name", ""),
                    "queued_at": now_iso(),
                }
            )

        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def handler(signum, frame):
    print("[watchlist] Timeout reached, shutting down", file=sys.stderr)
    sys.exit(0)


def main() -> str:
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(_DEADLINE_SEC)

    try:
        rules = yaml.safe_load(RULES_PATH.read_text())
    except Exception as e:
        return f"ERROR: {e}"

    state = load_state()
    sources = [s for s in rules.get("sources", []) if s.get("enabled")]
    all_items: List[dict] = []

    for src in sources:
        sid = src["id"]
        src_st = state.setdefault("sources", {}).setdefault(sid, {})
        last = src_st.get("last_checked", "")
        interval = src.get("poll_interval_sec", 3600)

        if last:
            try:
                elapsed = (
                    datetime.now(TZ_UTC8) - datetime.fromisoformat(last)
                ).total_seconds()
                if elapsed < interval:
                    continue
            except Exception:
                pass

        try:
            stype = src.get("type", "")
            if stype == "hackernews":
                items = fetch_hn(src, state)
            elif stype == "rss":
                items = fetch_rss(src, state)
            elif stype == "wallstreetcn":
                items = fetch_wallstreetcn(src, state)
            elif stype == "x_scrape":
                items = fetch_x_scrape(src, state, Path(__file__).parent)
            else:
                items = []
        except Exception as e:
            print(f"[watchlist] {sid}: fetch error {e}", file=sys.stderr)
            items = []

        if items:
            domain = src.get("target_domain", "")
            score_items(items, domain, rules)
            for it in items:
                it["target_domain"] = domain
            all_items.extend(items)

        src_st["last_checked"] = now_iso()
        time.sleep(0.5)

    # Push
    n_rt = push_realtime(all_items, rules)
    is_digest = datetime.now(TZ_UTC8).hour == 9 and datetime.now(TZ_UTC8).minute < 5
    n_dg = 0
    if is_digest:
        n_dg = 1 if push_digest(all_items, rules, state) else 0

    # Archive daily digest + queue high-score for ingest
    if all_items and (is_digest or any(it.get("score", 0) >= 8 for it in all_items)):
        archive_items(all_items, KB_PATH, state)

    # Cleanup old seen items
    cutoff = datetime.now(TZ_UTC8) - timedelta(
        hours=rules.get("push", {}).get("deduplication", {}).get("seen_ttl_hours", 168)
    )
    seen = state.get("seen_items", {})
    stale = []
    for k, v in seen.items():
        try:
            ts = datetime.fromisoformat(v[:19])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=TZ_UTC8)
            if ts < cutoff:
                stale.append(k)
        except Exception:
            pass
    for k in stale:
        del seen[k]

    save_state(state)
    signal.alarm(0)

    if not all_items:
        return SILENT
    return f"Watchlist: {len(all_items)} items, scored {sum(1 for it in all_items if it.get('score', 0) > 0)}, rt_push={n_rt}, digest={n_dg}"


if __name__ == "__main__":
    print(main())

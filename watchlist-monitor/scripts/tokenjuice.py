"""
TokenJuice — lightweight text compression for LLM context.
Rule-driven, deterministic, zero external dependencies.

Inspired by TokenJuice (MIT) and OpenHuman's compression layer.
Unlike the full TokenJuice CLI, this is a pure-function Python module
that compresses text before it enters an LLM prompt.

Rules are loaded from:
  1. Built-in defaults (this module)
  2. User rules:  ~/.config/tokenjuice/rules/<tool>.json
  3. Project rules: <project>/.tokenjuice/rules/<tool>.json
Later layers override earlier ones by rule key.

Usage:
    from tokenjuice import compress
    clean = compress(raw_text, tool="score_items")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in defaults
# ---------------------------------------------------------------------------

_DEFAULT_RULES: Dict[str, dict] = {
    "default": {
        "strip_html": True,
        "normalize_whitespace": True,
        "dedup_lines": True,
        "max_length": 8000,
        "keep_head": 2000,
        "keep_tail": 500,
    },
    "score_items": {
        "strip_html": True,
        "normalize_whitespace": True,
        "dedup_lines": True,
        "max_length": 3000,
        "keep_head": 1500,
        "keep_tail": 0,
        "strip_urls": False,
        "strip_boilerplate": True,
    },
    "ingest_source": {
        "strip_html": False,
        "normalize_whitespace": True,
        "dedup_lines": False,
        "max_length": 12000,
        "keep_head": 8000,
        "keep_tail": 2000,
        "preserve_markdown_links": True,
        "preserve_image_embeds": True,
    },
    "clip_extract": {
        "strip_html": True,
        "normalize_whitespace": True,
        "dedup_lines": True,
        "max_length": 16000,
        "keep_head": 12000,
        "keep_tail": 2000,
        "strip_boilerplate": True,
    },
}

# Common boilerplate patterns to remove
_BOILERPLATE = [
    r"Share\s+(this|on).*",
    r"Follow\s+us\s+on.*",
    r"Subscribe\s+to\s+our.*",
    r"Click\s+here\s+to\s+(read|learn|subscribe|sign|view).*",
    r"All\s+[Rr]ights\s+[Rr]eserved\.?",
    r"Copyright\s+\©?\s*\d{4}.*",
    r"^\s*Advertisement\s*$",
    r"^\s*Sponsored\s*$",
    r"Related\s+(Articles|Posts|Stories|Reading).*",
    r"You\s+might\s+also\s+(like|enjoy).*",
    r"Sign\s+up\s+for\s+our\s+(newsletter|daily).*",
    r"本文(来源|作者|责编).*",
    r"（(文|图).*?）",
]


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------


def _load_rules(tool: str) -> dict:
    """Load merged rules: built-in defaults ← user ← project."""
    rules = dict(_DEFAULT_RULES.get("default", {}))
    rules.update(_DEFAULT_RULES.get(tool, {}))

    for rules_dir in [
        Path.home() / ".config" / "tokenjuice" / "rules",
        Path(".tokenjuice") / "rules",
    ]:
        for path in [rules_dir / f"{tool}.json", rules_dir / "default.json"]:
            if path.exists():
                try:
                    rules.update(json.loads(path.read_text()))
                except Exception:
                    pass

    return rules


# ---------------------------------------------------------------------------
# Compression steps
# ---------------------------------------------------------------------------


def _strip_html(text: str) -> str:
    """Remove HTML tags, keep text content."""
    text = re.sub(
        r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(
        r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?div[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#?\w+;", " ", text)
    return text


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^[ \t]+|[ \t]+$", "", text, flags=re.MULTILINE)
    return text.strip()


def _dedup_lines(text: str) -> str:
    """Remove duplicate adjacent lines."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if result and stripped == result[-1].strip():
            continue
        if stripped or result:
            result.append(line)
    while result and not result[-1].strip():
        result.pop()
    return "\n".join(result)


def _strip_boilerplate(text: str) -> str:
    """Remove common boilerplate footer/header lines."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        if any(re.match(p, stripped, re.IGNORECASE) for p in _BOILERPLATE):
            continue
        result.append(line)
    return "\n".join(result)


def _preserve_embeds(text: str) -> Dict[str, str]:
    """Extract markdown image embeds and links, replace with placeholders."""
    embeds: Dict[str, str] = {}
    idx = 0

    def _save(m: re.Match) -> str:
        nonlocal idx
        key = f"__EMBED_{idx}__"
        embeds[key] = m.group(0)
        idx += 1
        return key

    text = re.sub(r"!\[\[raw/assets/[^\]]+\]\]", _save, text)
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", _save, text)
    return embeds


def _restore_embeds(text: str, embeds: Dict[str, str]) -> str:
    """Restore placeholders to original embed/link text."""
    for key, original in embeds.items():
        text = text.replace(key, original)
    return text


def _smart_truncate(text: str, max_len: int, keep_head: int, keep_tail: int) -> str:
    """Truncate text while keeping head and tail context."""
    if len(text) <= max_len:
        return text
    if keep_head + keep_tail >= max_len:
        return text[:max_len]

    head = text[:keep_head]
    tail = text[-keep_tail:] if keep_tail > 0 else ""

    # Try to break at paragraph boundary
    head_break = head.rfind("\n\n")
    if head_break > keep_head * 0.5:
        head = head[:head_break]
    tail_break = tail.find("\n\n") if tail else -1
    if tail_break > 0 and tail_break < len(tail) * 0.5:
        tail = tail[tail_break:]

    return f"{head}\n\n[... {len(text) - len(head) - len(tail)} chars truncated ...]\n\n{tail}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compress(text: str, tool: str = "default", max_length: Optional[int] = None) -> str:
    """Compress text for LLM context consumption.

    Args:
        text: Raw text to compress.
        tool: Rule set to apply (default, score_items, ingest_source, clip_extract).
        max_length: Override the max_length from rules.

    Returns:
        Compressed text suitable for LLM prompt injection.
    """
    if not text:
        return ""

    rules = _load_rules(tool)

    # Save embeds before compression
    preserve_links = rules.get("preserve_markdown_links", False)
    preserve_images = rules.get("preserve_image_embeds", False)
    embeds: Dict[str, str] = {}
    if preserve_images:
        embeds.update(_preserve_embeds(text))

    # Apply transforms
    if rules.get("strip_html", True):
        text = _strip_html(text)

    if rules.get("normalize_whitespace", True):
        text = _normalize_whitespace(text)

    if rules.get("strip_boilerplate", False):
        text = _strip_boilerplate(text)

    if rules.get("dedup_lines", False):
        text = _dedup_lines(text)

    # Restore embeds
    if embeds:
        text = _restore_embeds(text, embeds)

    # Truncate
    ml = max_length or rules.get("max_length", 8000)
    keep_head = rules.get("keep_head", ml // 2)
    keep_tail = rules.get("keep_tail", ml // 4)
    text = _smart_truncate(text, ml, keep_head, keep_tail)

    return text


def compress_for_tool(text: str, tool_name: str, command: str = "") -> str:
    """Compress text specifically for a known tool/command combination."""
    # Map tool+command to the right rule set
    if tool_name in ("score_items", "score"):
        return compress(text, "score_items")
    if tool_name in ("ingest", "ingest_source", "create_summary"):
        return compress(text, "ingest_source")
    if tool_name in ("clip", "extract"):
        return compress(text, "clip_extract")
    return compress(text, "default")


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample = """
    <div class="article-content">
    <p>Germany's 10-year bond yield dropped 4 basis points to 3.06%,
    extending earlier gains in the bund market.</p>
    <p>Iran has allowed 30 vessels to pass through the Strait of Hormuz
    since last night, according to Iranian state television.</p>
    <div class="related">Related Articles: More news from the region</div>
    <p>Copyright 2026 Bloomberg. All rights reserved.</p>
    </div>
    """
    print("=== Original ===")
    print(f"Length: {len(sample)} chars")
    print()
    print("=== score_items ===")
    result = compress(sample, "score_items")
    print(result)
    print(f"Length: {len(result)} chars")
    print(f"Reduction: {(1 - len(result) / max(len(sample), 1)) * 100:.0f}%")

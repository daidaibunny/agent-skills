#!/usr/bin/env python3
"""Export completed ChatGPT project chats from the active Chrome profile.

This script intentionally uses the already-authenticated Google Chrome session.
It requires Chrome's "Allow JavaScript from Apple Events" setting to be enabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_FRAGMENT = "/g/g-p-69e8a817b614819181a4aa9f6f2c6f80-bdi-agent"
TAB_FIELD_DELIMITER = "|||CHATGPT_EXPORT_FIELD|||"


class ChromeScriptError(RuntimeError):
	"""Raised when Chrome AppleScript or in-page JavaScript cannot run."""


@dataclass(frozen=True)
class ChromeTab:
	window_index: int
	tab_index: int
	url: str
	title: str


def run_osascript(script: str) -> str:
	result = subprocess.run(
		["osascript"],
		input=script,
		text=True,
		capture_output=True,
		check=False,
	)
	if result.returncode != 0:
		message = result.stderr.strip() or result.stdout.strip()
		raise ChromeScriptError(message)
	return result.stdout.strip()


def list_chrome_tabs() -> list[ChromeTab]:
	script = f'''
tell application "Google Chrome"
	set output to ""
	repeat with windowIndex from 1 to count of windows
		set currentWindow to window windowIndex
		repeat with tabIndex from 1 to count of tabs of currentWindow
			set currentTab to tab tabIndex of currentWindow
			set tabUrl to URL of currentTab
			set tabTitle to title of currentTab
			set output to output & windowIndex & "{TAB_FIELD_DELIMITER}" & tabIndex & "{TAB_FIELD_DELIMITER}" & tabUrl & "{TAB_FIELD_DELIMITER}" & tabTitle & linefeed
		end repeat
	end repeat
	return output
end tell
'''
	output = run_osascript(script)
	tabs: list[ChromeTab] = []
	for line in output.splitlines():
		parts = line.split(TAB_FIELD_DELIMITER, 3)
		if len(parts) != 4:
			continue
		window_index, tab_index, url, title = parts
		try:
			tabs.append(
				ChromeTab(
					window_index=int(window_index),
					tab_index=int(tab_index),
					url=url,
					title=title,
				),
			)
		except ValueError:
			continue
	return tabs


def js_string_literal(value: str) -> str:
	return json.dumps(value, ensure_ascii=False)


def execute_tab_javascript(tab: ChromeTab, javascript: str) -> str:
	script = f'''
tell application "Google Chrome"
	return execute tab {tab.tab_index} of window {tab.window_index} javascript {js_string_literal(javascript)}
end tell
'''
	return run_osascript(script)


SCRAPE_JAVASCRIPT = r'''
(() => {
	const textOf = (node) => (node?.innerText || node?.textContent || "").trim();
	const attr = (node, name) => node?.getAttribute?.(name) || null;
	const visible = (node) => {
		if (!node) return false;
		const style = window.getComputedStyle(node);
		const rect = node.getBoundingClientRect();
		return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
	};
	const allButtons = Array.from(document.querySelectorAll("button")).filter(visible);
	const buttonText = (button) => [
		button.getAttribute("aria-label") || "",
		button.getAttribute("title") || "",
		button.innerText || "",
		button.textContent || "",
	].join(" ").trim();
	const stopButtons = allButtons.filter((button) => /stop|停止|cancel|取消/i.test(buttonText(button)));
	const continueButtons = allButtons.filter((button) => (
		/continue generating|继续生成|继续/i.test(buttonText(button))
	));
	const streamingNodes = Array.from(document.querySelectorAll([
		".result-streaming",
		"[data-is-streaming='true']",
		"[aria-busy='true']",
		"[data-testid='stop-button']",
	].join(","))).filter(visible);
	const roleNodes = Array.from(document.querySelectorAll("[data-message-author-role]"));
	const messages = roleNodes.map((node, index) => {
		const role = attr(node, "data-message-author-role") || "unknown";
		const messageId = attr(node, "data-message-id") || attr(node.closest("[data-message-id]"), "data-message-id");
		const modelSlug = attr(node, "data-message-model-slug")
			|| attr(node.closest("[data-message-model-slug]"), "data-message-model-slug");
		return {
			index,
			role,
			message_id: messageId,
			model_slug: modelSlug,
			text: textOf(node),
		};
	}).filter((message) => message.text.length > 0);
	const assistantMessages = messages.filter((message) => message.role === "assistant");
	const userMessages = messages.filter((message) => message.role === "user");
	const pageMain = document.querySelector("main") || document.body;
	const payload = {
		url: window.location.href,
		title: document.title,
		scraped_at: new Date().toISOString(),
		is_generating: stopButtons.length > 0 || streamingNodes.length > 0,
		needs_continue: continueButtons.length > 0,
		stop_button_count: stopButtons.length,
		streaming_node_count: streamingNodes.length,
		continue_button_count: continueButtons.length,
		message_count: messages.length,
		user_message_count: userMessages.length,
		assistant_message_count: assistantMessages.length,
		last_user_text: userMessages.length ? userMessages[userMessages.length - 1].text : null,
		last_assistant_text: assistantMessages.length ? assistantMessages[assistantMessages.length - 1].text : null,
		messages,
		page_text_sha256: "",
	};
	payload.page_text_sha256 = "";
	return JSON.stringify(payload);
})()
'''


CLICK_CONTINUE_JAVASCRIPT = r'''
(() => {
	const visible = (node) => {
		if (!node) return false;
		const style = window.getComputedStyle(node);
		const rect = node.getBoundingClientRect();
		return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
	};
	const allButtons = Array.from(document.querySelectorAll("button")).filter(visible);
	const target = allButtons.find((button) => {
		const text = [
			button.getAttribute("aria-label") || "",
			button.getAttribute("title") || "",
			button.innerText || "",
			button.textContent || "",
		].join(" ");
		return /continue generating|继续生成|继续/i.test(text);
	});
	if (!target) return JSON.stringify({clicked: false});
	target.click();
	return JSON.stringify({clicked: true});
})()
'''


def scrape_tab(tab: ChromeTab) -> dict[str, Any]:
	raw = execute_tab_javascript(tab, SCRAPE_JAVASCRIPT)
	try:
		payload = json.loads(raw)
	except json.JSONDecodeError as exc:
		raise ChromeScriptError(f"Could not parse scraped JSON for tab {tab.url}: {exc}") from exc
	payload["window_index"] = tab.window_index
	payload["tab_index"] = tab.tab_index
	payload["initial_title"] = tab.title
	payload["initial_url"] = tab.url
	payload["content_sha256"] = hashlib.sha256(
		json.dumps(payload.get("messages", []), ensure_ascii=False, sort_keys=True).encode("utf-8"),
	).hexdigest()
	return payload


def click_continue(tab: ChromeTab) -> bool:
	raw = execute_tab_javascript(tab, CLICK_CONTINUE_JAVASCRIPT)
	try:
		return bool(json.loads(raw).get("clicked"))
	except json.JSONDecodeError:
		return False


def find_target_tabs(project_fragment: str, active_only: bool) -> list[ChromeTab]:
	tabs = list_chrome_tabs()
	targets = [tab for tab in tabs if project_fragment in tab.url]
	if active_only and targets:
		return targets[:1]
	return targets


def stable_signature(scraped_tabs: list[dict[str, Any]]) -> str:
	stable_payload = [
		{
			"url": tab.get("url"),
			"messages": tab.get("messages", []),
			"is_generating": tab.get("is_generating"),
			"needs_continue": tab.get("needs_continue"),
		}
		for tab in scraped_tabs
	]
	return hashlib.sha256(
		json.dumps(stable_payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
	).hexdigest()


def wait_and_scrape(
	project_fragment: str,
	active_only: bool,
	timeout_seconds: float,
	poll_seconds: float,
	settle_seconds: float,
	auto_continue: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
	deadline = time.monotonic() + timeout_seconds
	last_signature: str | None = None
	stable_since = time.monotonic()
	last_scrape: list[dict[str, Any]] = []
	continue_clicks = 0
	polls = 0

	while True:
		tabs = find_target_tabs(project_fragment, active_only)
		if not tabs:
			raise ChromeScriptError(f"No Chrome tabs matched project fragment: {project_fragment}")

		scraped = [scrape_tab(tab) for tab in tabs]
		polls += 1

		if auto_continue:
			for tab, payload in zip(tabs, scraped, strict=True):
				if payload.get("needs_continue"):
					if click_continue(tab):
						continue_clicks += 1
						time.sleep(min(2.0, poll_seconds))
						break

		signature = stable_signature(scraped)
		now = time.monotonic()
		if signature != last_signature:
			last_signature = signature
			stable_since = now
		last_scrape = scraped

		is_generating = any(tab.get("is_generating") for tab in scraped)
		needs_continue = any(tab.get("needs_continue") for tab in scraped)
		is_stable = now - stable_since >= settle_seconds
		if not is_generating and not needs_continue and is_stable:
			metadata = {
				"completed": True,
				"polls": polls,
				"continue_clicks": continue_clicks,
				"settle_seconds": settle_seconds,
				"timeout_seconds": timeout_seconds,
			}
			return scraped, metadata

		if now >= deadline:
			metadata = {
				"completed": False,
				"polls": polls,
				"continue_clicks": continue_clicks,
				"settle_seconds": settle_seconds,
				"timeout_seconds": timeout_seconds,
				"failure_reason": "timeout_waiting_for_complete_and_stable_output",
			}
			return last_scrape, metadata

		time.sleep(poll_seconds)


def write_export(path: Path, tabs: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	payload = {
		"exported_at": datetime.now(timezone.utc).isoformat(),
		"schema_version": 1,
		"source": "chatgpt_web_ui_chrome_apple_events",
		"metadata": metadata,
		"tabs": tabs,
	}
	if path.suffix.lower() == ".jsonl":
		with path.open("w", encoding="utf-8") as handle:
			for tab in tabs:
				handle.write(json.dumps(tab, ensure_ascii=False, sort_keys=True))
				handle.write("\n")
		return
	with path.open("w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
		handle.write("\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Wait for ChatGPT project tabs to finish generating and export visible messages.",
	)
	parser.add_argument("--output", required=True, help="Destination .json or .jsonl path.")
	parser.add_argument(
		"--project-fragment",
		default=DEFAULT_PROJECT_FRAGMENT,
		help="URL fragment used to select ChatGPT project tabs.",
	)
	parser.add_argument(
		"--active-tab-only",
		action="store_true",
		help="Export only the first matching project tab instead of all matching project tabs.",
	)
	parser.add_argument("--timeout-seconds", type=float, default=1200.0)
	parser.add_argument("--poll-seconds", type=float, default=5.0)
	parser.add_argument(
		"--settle-seconds",
		type=float,
		default=20.0,
		help="Require unchanged messages for this long after generation indicators disappear.",
	)
	parser.add_argument(
		"--no-auto-continue",
		action="store_true",
		help="Do not click visible Continue generating buttons.",
	)
	parser.add_argument(
		"--fail-on-incomplete",
		action="store_true",
		help="Exit non-zero when timeout occurs before completion/stability.",
	)
	return parser.parse_args(argv)


def main(argv: list[str]) -> int:
	args = parse_args(argv)
	try:
		tabs, metadata = wait_and_scrape(
			project_fragment=args.project_fragment,
			active_only=args.active_tab_only,
			timeout_seconds=args.timeout_seconds,
			poll_seconds=args.poll_seconds,
			settle_seconds=args.settle_seconds,
			auto_continue=not args.no_auto_continue,
		)
		write_export(Path(args.output), tabs, metadata)
	except ChromeScriptError as exc:
		print(f"error: {exc}", file=sys.stderr)
		if "No Chrome tabs matched" in str(exc):
			print("hint: open the required ChatGPT project tab, then rerun the script.", file=sys.stderr)
		else:
			print(
				"hint: enable Chrome > View > Developer > Allow JavaScript from Apple Events, "
				"then rerun the script.",
				file=sys.stderr,
			)
		return 2

	if args.fail_on_incomplete and not metadata.get("completed"):
		print(f"incomplete export written to {args.output}", file=sys.stderr)
		return 1
	print(f"export written to {args.output}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main(sys.argv[1:]))

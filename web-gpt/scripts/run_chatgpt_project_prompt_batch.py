#!/usr/bin/env python3
"""Run a batch of prompts in ChatGPT project tabs and export completed results."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_chatgpt_project_chats import (
	ChromeScriptError,
	ChromeTab,
	execute_tab_javascript,
	js_string_literal,
	scrape_tab,
)


DEFAULT_PROJECT_URL = (
	"https://chatgpt.com/g/g-p-69e8a817b614819181a4aa9f6f2c6f80-bdi-agent/project"
)
FIELD_DELIMITER = "|||CHATGPT_BATCH_FIELD|||"


@dataclass
class PromptCase:
	case_id: str
	prompt: str


@dataclass
class RunningCase:
	case: PromptCase
	tab: ChromeTab
	started_at: str
	submitted_at: str | None = None
	completed_at: str | None = None
	status: str = "opened"
	failure_reason: str | None = None
	continue_clicks: int = 0
	output_path: str | None = None
	last_signature: str | None = None
	started_monotonic: float = field(default_factory=time.monotonic)
	stable_since: float = field(default_factory=time.monotonic)


def utc_now() -> str:
	return datetime.now(timezone.utc).isoformat()


def sanitize_case_id(value: str) -> str:
	sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
	return sanitized or "prompt"


def load_prompts(path: Path) -> list[PromptCase]:
	text = path.read_text(encoding="utf-8")
	cases: list[PromptCase] = []
	if path.suffix.lower() == ".json":
		payload = json.loads(text)
		items = payload.get("prompts", payload) if isinstance(payload, dict) else payload
		if not isinstance(items, list):
			raise ValueError("JSON prompt file must be a list or an object with a prompts list.")
		for index, item in enumerate(items, start=1):
			if isinstance(item, str):
				case_id = f"prompt_{index:03d}"
				prompt = item
			elif isinstance(item, dict):
				case_id = str(item.get("id") or f"prompt_{index:03d}")
				prompt = str(item["prompt"])
			else:
				raise ValueError(f"Unsupported prompt item at index {index}: {item!r}")
			cases.append(PromptCase(case_id=sanitize_case_id(case_id), prompt=prompt))
	elif path.suffix.lower() == ".jsonl":
		for index, line in enumerate(text.splitlines(), start=1):
			line = line.strip()
			if not line:
				continue
			item = json.loads(line)
			if isinstance(item, str):
				case_id = f"prompt_{index:03d}"
				prompt = item
			else:
				case_id = str(item.get("id") or f"prompt_{index:03d}")
				prompt = str(item["prompt"])
			cases.append(PromptCase(case_id=sanitize_case_id(case_id), prompt=prompt))
	else:
		for index, line in enumerate(text.splitlines(), start=1):
			prompt = line.strip()
			if prompt:
				cases.append(PromptCase(case_id=f"prompt_{index:03d}", prompt=prompt))
	if not cases:
		raise ValueError("Prompt file did not contain any prompts.")
	return ensure_unique_case_ids(cases)


def ensure_unique_case_ids(cases: list[PromptCase]) -> list[PromptCase]:
	seen: dict[str, int] = {}
	result: list[PromptCase] = []
	for case in cases:
		count = seen.get(case.case_id, 0) + 1
		seen[case.case_id] = count
		case_id = case.case_id if count == 1 else f"{case.case_id}_{count}"
		result.append(PromptCase(case_id=case_id, prompt=case.prompt))
	return result


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


def open_project_tab(project_url: str, prompt: str) -> ChromeTab:
	url = f"{project_url}?prompt={urllib.parse.quote(prompt)}"
	script = f'''
tell application "Google Chrome"
	if (count of windows) = 0 then
		make new window
	end if
	set targetWindow to front window
	set newTab to make new tab at end of tabs of targetWindow with properties {{URL:{js_string_literal(url)}}}
	set active tab index of targetWindow to (count of tabs of targetWindow)
	return "1{FIELD_DELIMITER}" & (active tab index of targetWindow) & "{FIELD_DELIMITER}" & (URL of newTab) & "{FIELD_DELIMITER}" & (title of newTab)
end tell
'''
	raw = run_osascript(script)
	parts = raw.split(FIELD_DELIMITER, 3)
	if len(parts) != 4:
		raise ChromeScriptError(f"Could not parse opened tab reference: {raw}")
	return ChromeTab(
		window_index=int(parts[0]),
		tab_index=int(parts[1]),
		url=parts[2],
		title=parts[3],
	)


def wait_for_page_loaded(tab: ChromeTab, timeout_seconds: float) -> None:
	deadline = time.monotonic() + timeout_seconds
	while time.monotonic() < deadline:
		script = f'''
tell application "Google Chrome"
	return loading of tab {tab.tab_index} of window {tab.window_index}
end tell
'''
		if run_osascript(script).lower() == "false":
			return
		time.sleep(1.0)
	raise ChromeScriptError(f"Timed out waiting for tab to load: {tab.url}")


def send_prompt(tab: ChromeTab, prompt: str) -> dict[str, Any]:
	javascript = f'''
(() => {{
	const promptText = {js_string_literal(prompt)};
	const visible = (node) => {{
		if (!node) return false;
		const style = window.getComputedStyle(node);
		const rect = node.getBoundingClientRect();
		return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
	}};
	const textOf = (node) => (node?.innerText || node?.textContent || node?.value || "").trim();
	const composer = document.querySelector("#prompt-textarea")
		|| document.querySelector("[data-testid='prompt-textarea']")
		|| document.querySelector("[contenteditable='true']")
		|| document.querySelector("textarea");
	if (!composer) return JSON.stringify({{submitted: false, reason: "composer_not_found"}});
	const composerText = textOf(composer);
	if (!composerText.includes(promptText)) {{
		composer.focus();
		document.execCommand("selectAll", false, null);
		document.execCommand("insertText", false, promptText);
		composer.dispatchEvent(new InputEvent("input", {{bubbles: true, inputType: "insertText", data: promptText}}));
	}}
	const buttons = Array.from(document.querySelectorAll("button")).filter(visible);
	const sendButton = buttons.find((button) => {{
		const label = [
			button.getAttribute("aria-label") || "",
			button.getAttribute("title") || "",
			button.innerText || "",
			button.textContent || "",
			button.getAttribute("data-testid") || "",
		].join(" ");
		return /send|发送|submit|composer-submit-button/i.test(label) && !button.disabled;
	}});
	if (!sendButton) {{
		return JSON.stringify({{
			submitted: false,
			reason: "send_button_not_found_or_disabled",
			composer_text: textOf(composer),
		}});
	}}
	sendButton.click();
	return JSON.stringify({{submitted: true, composer_text: textOf(composer)}});
}})()
'''
	raw = execute_tab_javascript(tab, javascript)
	return json.loads(raw)


def click_continue(tab: ChromeTab) -> bool:
	javascript = r'''
(() => {
	const visible = (node) => {
		if (!node) return false;
		const style = window.getComputedStyle(node);
		const rect = node.getBoundingClientRect();
		return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
	};
	const target = Array.from(document.querySelectorAll("button")).filter(visible).find((button) => {
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
	return bool(json.loads(execute_tab_javascript(tab, javascript)).get("clicked"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	temp_path = path.with_suffix(f"{path.suffix}.tmp")
	with temp_path.open("w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
		handle.write("\n")
	temp_path.replace(path)


def case_payload(run_id: str, running: RunningCase, scrape: dict[str, Any]) -> dict[str, Any]:
	return {
		"schema_version": 1,
		"run_id": run_id,
		"case_id": running.case.case_id,
		"prompt": running.case.prompt,
		"status": running.status,
		"failure_reason": running.failure_reason,
		"started_at": running.started_at,
		"submitted_at": running.submitted_at,
		"completed_at": running.completed_at,
		"continue_clicks": running.continue_clicks,
		"tab": scrape,
	}


def signature(scrape: dict[str, Any]) -> str:
	return str(scrape.get("content_sha256") or scrape.get("message_count") or "")


def run_batch(args: argparse.Namespace) -> dict[str, Any]:
	prompts = load_prompts(Path(args.prompt_file))
	output_dir = Path(args.output_dir)
	run_id = args.run_id or datetime.now(timezone.utc).strftime("web_gpt_%Y%m%d_%H%M%S")
	items_dir = output_dir / run_id / "items"
	manifest_path = output_dir / run_id / "manifest.json"
	pending = list(prompts)
	running: list[RunningCase] = []
	finished: list[RunningCase] = []
	started_at = utc_now()

	def write_manifest() -> None:
		write_json(
			manifest_path,
			{
				"schema_version": 1,
				"run_id": run_id,
				"started_at": started_at,
				"updated_at": utc_now(),
				"project_url": args.project_url,
				"max_concurrent": args.max_concurrent,
				"timeout_seconds": args.timeout_seconds,
				"settle_seconds": args.settle_seconds,
				"counts": {
					"total": len(prompts),
					"pending": len(pending),
					"running": len(running),
					"finished": len(finished),
					"succeeded": sum(1 for item in finished if item.status == "completed"),
					"failed": sum(1 for item in finished if item.status == "failed"),
				},
				"items": [
					{
						"case_id": item.case.case_id,
						"status": item.status,
						"failure_reason": item.failure_reason,
						"started_at": item.started_at,
						"submitted_at": item.submitted_at,
						"completed_at": item.completed_at,
						"output_path": item.output_path,
						"url": item.tab.url,
					}
					for item in [*running, *finished]
				],
			},
		)

	while pending or running:
		while pending and len(running) < args.max_concurrent:
			case = pending.pop(0)
			tab = open_project_tab(args.project_url, case.prompt)
			wait_for_page_loaded(tab, args.page_load_timeout_seconds)
			running_case = RunningCase(case=case, tab=tab, started_at=utc_now())
			submit_result = send_prompt(tab, case.prompt)
			if submit_result.get("submitted"):
				running_case.status = "submitted"
				running_case.submitted_at = utc_now()
			else:
				running_case.status = "failed"
				running_case.failure_reason = str(submit_result.get("reason") or "submit_failed")
				running_case.completed_at = utc_now()
				running_case.output_path = str(items_dir / f"{case.case_id}.json")
				write_json(Path(running_case.output_path), {"submit_result": submit_result})
				finished.append(running_case)
				continue
			running.append(running_case)
			write_manifest()

		now = time.monotonic()
		still_running: list[RunningCase] = []
		for item in running:
			scrape = scrape_tab(item.tab)
			if scrape.get("needs_continue") and click_continue(item.tab):
				item.continue_clicks += 1
				item.last_signature = None
				item.stable_since = time.monotonic()
				still_running.append(item)
				continue

			current_signature = signature(scrape)
			if current_signature != item.last_signature:
				item.last_signature = current_signature
				item.stable_since = now

			is_stable = now - item.stable_since >= args.settle_seconds
			is_complete = (
				not scrape.get("is_generating")
				and not scrape.get("needs_continue")
				and is_stable
				and scrape.get("assistant_message_count", 0) > 0
			)
			is_timeout = now - item.started_monotonic > args.timeout_seconds
			if is_complete:
				item.status = "completed"
				item.completed_at = utc_now()
				item.output_path = str(items_dir / f"{item.case.case_id}.json")
				write_json(Path(item.output_path), case_payload(run_id, item, scrape))
				finished.append(item)
			elif is_timeout:
				item.status = "failed"
				item.failure_reason = "timeout_waiting_for_complete_and_stable_output"
				item.completed_at = utc_now()
				item.output_path = str(items_dir / f"{item.case.case_id}.json")
				write_json(Path(item.output_path), case_payload(run_id, item, scrape))
				finished.append(item)
			else:
				still_running.append(item)
		running = still_running
		write_manifest()
		if pending or running:
			time.sleep(args.poll_seconds)

	return json.loads(manifest_path.read_text(encoding="utf-8"))


def parse_args(argv: list[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Run ChatGPT project prompts in parallel browser tabs and export results.",
	)
	parser.add_argument("--prompt-file", required=True, help="JSON, JSONL, or newline text prompt file.")
	parser.add_argument("--output-dir", required=True, help="Directory for run manifest and item JSON files.")
	parser.add_argument("--project-url", default=DEFAULT_PROJECT_URL)
	parser.add_argument("--run-id", default=None)
	parser.add_argument("--max-concurrent", type=int, default=3)
	parser.add_argument("--timeout-seconds", type=float, default=1800.0)
	parser.add_argument("--page-load-timeout-seconds", type=float, default=90.0)
	parser.add_argument("--poll-seconds", type=float, default=5.0)
	parser.add_argument("--settle-seconds", type=float, default=20.0)
	return parser.parse_args(argv)


def main(argv: list[str]) -> int:
	args = parse_args(argv)
	if args.max_concurrent < 1:
		print("error: --max-concurrent must be >= 1", file=sys.stderr)
		return 2
	try:
		manifest = run_batch(args)
	except (ChromeScriptError, ValueError, json.JSONDecodeError) as exc:
		print(f"error: {exc}", file=sys.stderr)
		print(
			"hint: this script needs an authenticated Chrome window and Chrome > View > "
			"Developer > Allow JavaScript from Apple Events enabled.",
			file=sys.stderr,
		)
		return 2

	print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
	return 0 if manifest["counts"]["failed"] == 0 else 1


if __name__ == "__main__":
	raise SystemExit(main(sys.argv[1:]))

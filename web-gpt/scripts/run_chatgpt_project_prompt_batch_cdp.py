#!/usr/bin/env python3
"""Run ChatGPT project prompt batches through an isolated CDP Chrome instance."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cdp_client import (
	CdpError,
	CdpTarget,
	create_target,
	evaluate,
	list_targets,
	navigate_target,
	wait_for_ready_state,
)


DEFAULT_PROJECT_URL = (
	"https://chatgpt.com/g/g-p-69e8a817b614819181a4aa9f6f2c6f80-bdi-agent/project"
)
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


@dataclass(frozen=True)
class PromptCase:
	case_id: str
	prompt: str


@dataclass
class RunningCase:
	case: PromptCase
	target: CdpTarget
	started_at: str
	started_monotonic: float = field(default_factory=time.monotonic)
	submitted_at: str | None = None
	completed_at: str | None = None
	status: str = "opened"
	failure_reason: str | None = None
	continue_clicks: int = 0
	output_path: str | None = None
	last_signature: str | None = None
	stable_since: float = field(default_factory=time.monotonic)


def utc_now() -> str:
	return datetime.now(timezone.utc).isoformat()


def js_string_literal(value: str) -> str:
	return json.dumps(value, ensure_ascii=False)


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


SEND_PROMPT_JAVASCRIPT = r'''
(async () => {
	const promptText = __PROMPT_TEXT__;
	const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
	const visible = (node) => {
		if (!node) return false;
		const style = window.getComputedStyle(node);
		const rect = node.getBoundingClientRect();
		return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
	};
	const textOf = (node) => (node?.innerText || node?.textContent || node?.value || "").trim();
	let composer = null;
	for (let attempt = 0; attempt < 120; attempt += 1) {
		const candidates = [
			...document.querySelectorAll("#prompt-textarea"),
			...document.querySelectorAll("[data-testid='prompt-textarea']"),
			...document.querySelectorAll("[contenteditable='true']"),
			...document.querySelectorAll("textarea"),
		];
		composer = candidates.find(visible) || null;
		if (composer) break;
		await sleep(500);
	}
	if (!composer) {
		return JSON.stringify({
			submitted: false,
			reason: "composer_not_found",
			url: window.location.href,
			title: document.title,
			body_text_sample: textOf(document.body).slice(0, 500),
		});
	}
	const currentText = textOf(composer);
	if (!currentText.includes(promptText)) {
		composer.focus();
		document.execCommand("selectAll", false, null);
		document.execCommand("insertText", false, promptText);
		composer.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: promptText}));
	}
	let sendButton = null;
	for (let attempt = 0; attempt < 50; attempt += 1) {
		const buttons = Array.from(document.querySelectorAll("button")).filter(visible);
		sendButton = buttons.find((button) => {
			const label = [
				button.id || "",
				button.getAttribute("aria-label") || "",
				button.getAttribute("title") || "",
				button.innerText || "",
				button.textContent || "",
				button.getAttribute("data-testid") || "",
			].join(" ");
			return /send|发送|submit|composer-submit-button/i.test(label) && !button.disabled;
		});
		if (sendButton) break;
		await sleep(100);
	}
	if (!sendButton) {
		return JSON.stringify({
			submitted: false,
			reason: "send_button_not_found_or_disabled",
			composer_text: textOf(composer),
			url: window.location.href,
			title: document.title,
		});
	}
	sendButton.click();
	return JSON.stringify({submitted: true, composer_text: textOf(composer), url: window.location.href});
})()
'''


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
	};
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


def find_existing_project_target(project_url: str, cdp_url: str) -> CdpTarget | None:
	project_prefix = project_url.rsplit("/project", 1)[0]
	for target in list_targets(cdp_url):
		try:
			href = str(evaluate(target, "window.location.href", timeout_seconds=5))
		except CdpError:
			href = target.url
		if href.startswith(project_prefix):
			return target
	return None


def open_project_target(project_url: str, cdp_url: str) -> CdpTarget:
	target = find_existing_project_target(project_url, cdp_url)
	if target is None:
		target = create_target(project_url, cdp_url=cdp_url)
	wait_for_ready_state(target, timeout_seconds=120)
	return target


def open_project_new_chat_in_same_tab(target: CdpTarget, project_url: str) -> CdpTarget:
	target = navigate_target(target, project_url)
	wait_for_ready_state(target, timeout_seconds=120)
	return target


def send_prompt(target: CdpTarget, prompt: str) -> dict[str, Any]:
	raw = evaluate(
		target,
		SEND_PROMPT_JAVASCRIPT.replace("__PROMPT_TEXT__", js_string_literal(prompt)),
		timeout_seconds=30,
	)
	return json.loads(str(raw))


def scrape_target(target: CdpTarget) -> dict[str, Any]:
	raw = evaluate(target, SCRAPE_JAVASCRIPT, timeout_seconds=30)
	payload = json.loads(str(raw))
	payload["target_id"] = target.id
	payload["initial_url"] = target.url
	payload["initial_title"] = target.title
	payload["content_sha256"] = hashlib.sha256(
		json.dumps(payload.get("messages", []), ensure_ascii=False, sort_keys=True).encode("utf-8"),
	).hexdigest()
	return payload


def click_continue(target: CdpTarget) -> bool:
	raw = evaluate(target, CLICK_CONTINUE_JAVASCRIPT, timeout_seconds=30)
	try:
		return bool(json.loads(str(raw)).get("clicked"))
	except json.JSONDecodeError:
		return False


def write_json(path: Path, payload: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	temp_path = path.with_suffix(f"{path.suffix}.tmp")
	with temp_path.open("w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
		handle.write("\n")
	temp_path.replace(path)


def signature(scrape: dict[str, Any]) -> str:
	return str(scrape.get("content_sha256") or scrape.get("message_count") or "")


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
		"target": scrape,
	}

def normalize_message_text(value: str) -> str:
	return re.sub(r"\s+", " ", str(value or "")).strip()


def user_message_matches_prompt(message_text: str, prompt: str) -> bool:
	"""
	Match submitted prompts after ChatGPT's DOM extraction normalizes whitespace.

	Long prompts can be accepted by the web interface while the visible message text
	is reflowed by the DOM scraper. Requiring byte-for-byte equality makes the
	runner report false submit failures, so use exact normalized equality first and
	then a conservative prefix/suffix/length check for large prompts.
	"""
	normalized_message = normalize_message_text(message_text)
	normalized_prompt = normalize_message_text(prompt)
	if normalized_message == normalized_prompt:
		return True
	if len(normalized_prompt) < 1000:
		return False
	prefix = normalized_prompt[:500]
	suffix = normalized_prompt[-500:]
	message_length = len(normalized_message)
	prompt_length = len(normalized_prompt)
	return (
		normalized_message.startswith(prefix)
		and normalized_message.endswith(suffix)
		and message_length >= int(prompt_length * 0.9)
	)


def count_user_prompt(scrape: dict[str, Any], prompt: str) -> int:
	return sum(
		1
		for message in scrape.get("messages", [])
		if message.get("role") == "user"
		and user_message_matches_prompt(str(message.get("text") or ""), prompt)
	)


def wait_for_submission(
	*,
	target: CdpTarget,
	prompt: str,
	baseline_prompt_count: int,
	timeout_seconds: float = 20.0,
	poll_seconds: float = 1.0,
) -> bool:
	deadline = time.monotonic() + timeout_seconds
	while time.monotonic() < deadline:
		try:
			scrape = scrape_target(target)
		except CdpError:
			time.sleep(poll_seconds)
			continue
		if count_user_prompt(scrape, prompt) > baseline_prompt_count:
			return True
		time.sleep(poll_seconds)
	return False


def wait_for_case_completion(
	*,
	item: RunningCase,
	run_id: str,
	items_dir: Path,
	timeout_seconds: float,
	poll_seconds: float,
	settle_seconds: float,
	baseline_assistant_count: int,
) -> RunningCase:
	item.last_signature = None
	item.stable_since = time.monotonic()
	while True:
		now = time.monotonic()
		try:
			scrape = scrape_target(item.target)
		except CdpError as exc:
			item.status = "failed"
			item.failure_reason = f"scrape_exception: {exc}"
			item.completed_at = utc_now()
			item.output_path = str(items_dir / f"{item.case.case_id}.json")
			write_json(Path(item.output_path), {"failure_reason": item.failure_reason})
			return item

		if scrape.get("needs_continue") and click_continue(item.target):
			item.continue_clicks += 1
			item.last_signature = None
			item.stable_since = time.monotonic()
			time.sleep(poll_seconds)
			continue

		current_signature = signature(scrape)
		if current_signature != item.last_signature:
			item.last_signature = current_signature
			item.stable_since = now

		is_stable = now - item.stable_since >= settle_seconds
		has_new_assistant = scrape.get("assistant_message_count", 0) > baseline_assistant_count
		has_prompt = count_user_prompt(scrape, item.case.prompt) > 0
		is_complete = (
			not scrape.get("is_generating")
			and not scrape.get("needs_continue")
			and is_stable
			and has_prompt
			and has_new_assistant
		)
		is_timeout = now - item.started_monotonic > timeout_seconds
		if is_complete:
			item.status = "completed"
			item.completed_at = utc_now()
			item.output_path = str(items_dir / f"{item.case.case_id}.json")
			write_json(Path(item.output_path), case_payload(run_id, item, scrape))
			return item
		if is_timeout:
			item.status = "failed"
			item.failure_reason = "timeout_waiting_for_complete_and_stable_output"
			item.completed_at = utc_now()
			item.output_path = str(items_dir / f"{item.case.case_id}.json")
			write_json(Path(item.output_path), case_payload(run_id, item, scrape))
			return item
		time.sleep(poll_seconds)


def run_batch(args: argparse.Namespace) -> dict[str, Any]:
	prompts = load_prompts(Path(args.prompt_file))
	output_dir = Path(args.output_dir)
	run_id = args.run_id or datetime.now(timezone.utc).strftime("web_gpt_%Y%m%d_%H%M%S")
	items_dir = output_dir / run_id / "items"
	manifest_path = output_dir / run_id / "manifest.json"
	finished: list[RunningCase] = []
	started_at = utc_now()
	target = open_project_target(args.project_url, args.cdp_url)

	def write_manifest(current: RunningCase | None = None, pending_count: int = 0) -> None:
		active = [current] if current else []
		write_json(
			manifest_path,
			{
				"schema_version": 1,
				"run_id": run_id,
				"started_at": started_at,
				"updated_at": utc_now(),
				"project_url": args.project_url,
				"cdp_url": args.cdp_url,
				"mode": "single_window_single_tab_project_new_chat",
				"timeout_seconds": args.timeout_seconds,
				"settle_seconds": args.settle_seconds,
				"counts": {
					"total": len(prompts),
					"pending": pending_count,
					"running": len(active),
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
						"initial_url": item.target.url,
					}
					for item in [*active, *finished]
				],
			},
		)

	for index, case in enumerate(prompts):
		target = open_project_new_chat_in_same_tab(target, args.project_url)
		baseline = scrape_target(target)
		baseline_prompt_count = count_user_prompt(baseline, case.prompt)
		item = RunningCase(case=case, target=target, started_at=utc_now())
		try:
			submit_result = send_prompt(target, case.prompt)
		except (CdpError, json.JSONDecodeError) as exc:
			submit_result = {"submitted": False, "reason": f"submit_exception: {exc}"}

		submitted = wait_for_submission(
			target=target,
			prompt=case.prompt,
			baseline_prompt_count=baseline_prompt_count,
		)
		if not submitted:
			item.status = "failed"
			item.failure_reason = str(submit_result.get("reason") or "submit_failed")
			item.completed_at = utc_now()
			item.output_path = str(items_dir / f"{case.case_id}.json")
			write_json(Path(item.output_path), {"submit_result": submit_result})
			finished.append(item)
			write_manifest(None, pending_count=len(prompts) - index - 1)
			break

		item.status = "submitted"
		item.submitted_at = utc_now()
		write_manifest(item, pending_count=len(prompts) - index - 1)
		item = wait_for_case_completion(
			item=item,
			run_id=run_id,
			items_dir=items_dir,
			timeout_seconds=args.timeout_seconds,
			poll_seconds=args.poll_seconds,
			settle_seconds=args.settle_seconds,
			baseline_assistant_count=baseline.get("assistant_message_count", 0),
		)
		finished.append(item)
		write_manifest(None, pending_count=len(prompts) - index - 1)
		if item.status != "completed":
			break

	return json.loads(manifest_path.read_text(encoding="utf-8"))


def parse_args(argv: list[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Run ChatGPT project prompts through the isolated web-gpt Chrome instance.",
	)
	parser.add_argument("--prompt-file", required=True, help="JSON, JSONL, or newline text prompt file.")
	parser.add_argument("--output-dir", required=True, help="Directory for run manifest and item JSON files.")
	parser.add_argument("--project-url", default=DEFAULT_PROJECT_URL)
	parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
	parser.add_argument("--run-id", default=None)
	parser.add_argument("--timeout-seconds", type=float, default=1800.0)
	parser.add_argument("--poll-seconds", type=float, default=5.0)
	parser.add_argument("--settle-seconds", type=float, default=20.0)
	return parser.parse_args(argv)


def main(argv: list[str]) -> int:
	args = parse_args(argv)
	try:
		manifest = run_batch(args)
	except (CdpError, ValueError, json.JSONDecodeError) as exc:
		print(f"error: {exc}", file=sys.stderr)
		print(
			"hint: launch the isolated browser with launch_web_gpt_chrome.py and log in once.",
			file=sys.stderr,
		)
		return 2
	print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
	return 0 if manifest["counts"]["failed"] == 0 else 1


if __name__ == "__main__":
	raise SystemExit(main(sys.argv[1:]))

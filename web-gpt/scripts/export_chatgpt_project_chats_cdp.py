#!/usr/bin/env python3
"""Export completed ChatGPT project chats from the isolated web-gpt Chrome instance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cdp_client import CdpError, CdpTarget, evaluate, list_targets
from run_chatgpt_project_prompt_batch_cdp import CLICK_CONTINUE_JAVASCRIPT, SCRAPE_JAVASCRIPT


DEFAULT_PROJECT_FRAGMENT = "/g/g-p-69e8a817b614819181a4aa9f6f2c6f80-bdi-agent"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


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


def find_project_targets(cdp_url: str, project_fragment: str) -> list[CdpTarget]:
	return [target for target in list_targets(cdp_url) if project_fragment in target.url]


def stable_signature(scraped_targets: list[dict[str, Any]]) -> str:
	stable_payload = [
		{
			"url": target.get("url"),
			"messages": target.get("messages", []),
			"is_generating": target.get("is_generating"),
			"needs_continue": target.get("needs_continue"),
		}
		for target in scraped_targets
	]
	return hashlib.sha256(
		json.dumps(stable_payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
	).hexdigest()


def wait_and_scrape(
	*,
	cdp_url: str,
	project_fragment: str,
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
		targets = find_project_targets(cdp_url, project_fragment)
		if not targets:
			raise CdpError(f"No project tabs matched fragment: {project_fragment}")
		scraped = [scrape_target(target) for target in targets]
		polls += 1

		if auto_continue:
			for target, payload in zip(targets, scraped, strict=True):
				if payload.get("needs_continue") and click_continue(target):
					continue_clicks += 1
					time.sleep(min(2.0, poll_seconds))
					break

		signature = stable_signature(scraped)
		now = time.monotonic()
		if signature != last_signature:
			last_signature = signature
			stable_since = now
		last_scrape = scraped

		is_generating = any(target.get("is_generating") for target in scraped)
		needs_continue = any(target.get("needs_continue") for target in scraped)
		is_stable = now - stable_since >= settle_seconds
		if not is_generating and not needs_continue and is_stable:
			return scraped, {
				"completed": True,
				"polls": polls,
				"continue_clicks": continue_clicks,
				"settle_seconds": settle_seconds,
				"timeout_seconds": timeout_seconds,
			}

		if now >= deadline:
			return last_scrape, {
				"completed": False,
				"polls": polls,
				"continue_clicks": continue_clicks,
				"settle_seconds": settle_seconds,
				"timeout_seconds": timeout_seconds,
				"failure_reason": "timeout_waiting_for_complete_and_stable_output",
			}

		time.sleep(poll_seconds)


def write_export(path: Path, targets: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	payload = {
		"exported_at": datetime.now(timezone.utc).isoformat(),
		"schema_version": 1,
		"source": "chatgpt_web_ui_isolated_chrome_cdp",
		"metadata": metadata,
		"targets": targets,
	}
	if path.suffix.lower() == ".jsonl":
		with path.open("w", encoding="utf-8") as handle:
			for target in targets:
				handle.write(json.dumps(target, ensure_ascii=False, sort_keys=True))
				handle.write("\n")
		return
	with path.open("w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
		handle.write("\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Wait for isolated web-gpt project tabs to finish and export visible messages.",
	)
	parser.add_argument("--output", required=True, help="Destination .json or .jsonl path.")
	parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
	parser.add_argument("--project-fragment", default=DEFAULT_PROJECT_FRAGMENT)
	parser.add_argument("--timeout-seconds", type=float, default=1200.0)
	parser.add_argument("--poll-seconds", type=float, default=5.0)
	parser.add_argument("--settle-seconds", type=float, default=20.0)
	parser.add_argument("--no-auto-continue", action="store_true")
	parser.add_argument("--fail-on-incomplete", action="store_true")
	return parser.parse_args(argv)


def main(argv: list[str]) -> int:
	args = parse_args(argv)
	try:
		targets, metadata = wait_and_scrape(
			cdp_url=args.cdp_url,
			project_fragment=args.project_fragment,
			timeout_seconds=args.timeout_seconds,
			poll_seconds=args.poll_seconds,
			settle_seconds=args.settle_seconds,
			auto_continue=not args.no_auto_continue,
		)
		write_export(Path(args.output), targets, metadata)
	except (CdpError, json.JSONDecodeError) as exc:
		print(f"error: {exc}", file=sys.stderr)
		print(
			"hint: launch the isolated browser with launch_web_gpt_chrome.py and log in once.",
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

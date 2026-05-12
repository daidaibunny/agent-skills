#!/usr/bin/env python3
"""Fetch unresolved feedback items through the admin API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


@dataclass(frozen=True)
class Config:
	api_base_url: str
	admin_user: str
	admin_password: str
	api_token: str | None
	timeout_seconds: float


class ApiError(RuntimeError):
	"""Raised when an API request fails."""



def require_env(name: str) -> str:
	value = os.environ.get(name, "").strip()
	if not value:
		raise ApiError(f"Missing required environment variable: {name}")
	return value



def build_config(timeout_seconds: float) -> Config:
	api_base_url = require_env("FEEDBACK_API_BASE_URL").rstrip("/")
	admin_user = require_env("FEEDBACK_ADMIN_USER")
	admin_password = require_env("FEEDBACK_ADMIN_PASSWORD")
	api_token = os.environ.get("FEEDBACK_API_TOKEN")
	return Config(
		api_base_url=api_base_url,
		admin_user=admin_user,
		admin_password=admin_password,
		api_token=api_token.strip() if api_token else None,
		timeout_seconds=timeout_seconds,
	)



def make_headers(config: Config) -> dict[str, str]:
	headers = {"Content-Type": "application/json"}
	if config.api_token:
		headers["X-API-Key"] = config.api_token
	return headers



def api_request(
	opener: request.OpenerDirector,
	config: Config,
	method: str,
	path: str,
	payload: dict[str, Any] | None = None,
) -> Any:
	url = parse.urljoin(f"{config.api_base_url}/", path.lstrip("/"))
	body = None
	if payload is not None:
		body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
	request_obj = request.Request(
		url=url,
		data=body,
		method=method,
		headers=make_headers(config),
	)
	try:
		with opener.open(request_obj, timeout=config.timeout_seconds) as response:
			raw = response.read().decode("utf-8")
	except error.HTTPError as exc:
		message = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
		raise ApiError(f"API {method} {path} failed: HTTP {exc.code} {message}") from exc
	except error.URLError as exc:
		raise ApiError(f"API {method} {path} failed: {exc.reason}") from exc

	if not raw:
		return None

	try:
		return json.loads(raw)
	except json.JSONDecodeError as exc:
		raise ApiError(f"Invalid JSON from API {method} {path}: {raw[:200]}") from exc



def login_admin(opener: request.OpenerDirector, config: Config) -> None:
	api_request(
		opener,
		config,
		"POST",
		"/api/auth/login",
		{
			"user_id": config.admin_user,
			"password": config.admin_password,
		},
	)



def fetch_open_feedback(opener: request.OpenerDirector, config: Config) -> list[dict[str, Any]]:
	items = api_request(opener, config, "GET", "/api/admin/feedback")
	if not isinstance(items, list):
		raise ApiError("Unexpected response shape from /api/admin/feedback.")
	return [item for item in items if isinstance(item, dict) and item.get("resolved_at") is None]


def is_system_feedback_item(item: dict[str, Any]) -> bool:
	if bool(item.get("is_system")):
		return True
	category = str(item.get("category", "")).strip().upper()
	source = str(item.get("source", "")).strip().upper()
	message = str(item.get("message", ""))
	return (
		category.startswith("SYSTEM_")
		or source in {"SYSTEM", "API_MONITOR", "TRADING_AGENT"}
		or message.startswith("[SYSTEM]")
	)



def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Fetch unresolved feedback items from the admin API.",
	)
	parser.add_argument("--feedback-id", type=int, help="Select one unresolved feedback by ID.")
	parser.add_argument(
		"--pick-latest",
		action="store_true",
		help="Select the latest unresolved feedback item.",
	)
	parser.add_argument(
		"--all",
		action="store_true",
		help="Return all unresolved feedback items.",
	)
	parser.add_argument(
		"--include-system",
		action="store_true",
		help="Include system feedback items in unresolved results.",
	)
	parser.add_argument(
		"--timeout",
		type=float,
		default=20.0,
		help="HTTP timeout in seconds.",
	)
	return parser.parse_args()



def main() -> int:
	args = parse_args()
	mode_count = int(bool(args.feedback_id)) + int(args.pick_latest) + int(args.all)
	if mode_count > 1:
		print("Only one of --feedback-id/--pick-latest/--all can be used.", file=sys.stderr)
		return 2

	try:
		config = build_config(args.timeout)
	except ApiError as exc:
		print(str(exc), file=sys.stderr)
		return 2

	opener = request.build_opener(request.HTTPCookieProcessor())
	try:
		login_admin(opener, config)
		open_items = fetch_open_feedback(opener, config)
	except ApiError as exc:
		print(str(exc), file=sys.stderr)
		return 1

	if not args.include_system:
		open_items = [item for item in open_items if not is_system_feedback_item(item)]

	if args.all:
		print(json.dumps({"count": len(open_items), "items": open_items}, ensure_ascii=False, indent=2))
		return 0

	if args.feedback_id is not None:
		for item in open_items:
			if item.get("id") == args.feedback_id:
				print(json.dumps(item, ensure_ascii=False, indent=2))
				return 0
		print(f"Feedback #{args.feedback_id} is not unresolved or does not exist.", file=sys.stderr)
		return 4

	if args.pick_latest:
		if not open_items:
			print(json.dumps({"count": 0, "item": None}, ensure_ascii=False, indent=2))
			return 0
		print(json.dumps({"count": len(open_items), "item": open_items[0]}, ensure_ascii=False, indent=2))
		return 0

	print(
		json.dumps(
			{
				"count": len(open_items),
				"first_open_feedback_id": open_items[0]["id"] if open_items else None,
			},
			ensure_ascii=False,
			indent=2,
		),
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

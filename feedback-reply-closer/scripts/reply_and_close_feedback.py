#!/usr/bin/env python3
"""Send an approved admin reply and close a feedback item."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request


APPROVAL_PATTERN = re.compile(r"^\s*批准并执行\s*#(\d+)\s*$")


@dataclass(frozen=True)
class Config:
	api_base_url: str
	admin_user: str
	admin_password: str
	api_token: str | None
	timeout_seconds: float


class ReplyError(RuntimeError):
	"""Raised when reply sending cannot proceed."""



def require_env(name: str) -> str:
	value = os.environ.get(name, "").strip()
	if not value:
		raise ReplyError(f"Missing required environment variable: {name}")
	return value



def build_config(timeout_seconds: float) -> Config:
	base_url = require_env("FEEDBACK_API_BASE_URL").rstrip("/")
	admin_user = require_env("FEEDBACK_ADMIN_USER")
	admin_password = require_env("FEEDBACK_ADMIN_PASSWORD")
	api_token = os.environ.get("FEEDBACK_API_TOKEN")
	return Config(
		api_base_url=base_url,
		admin_user=admin_user,
		admin_password=admin_password,
		api_token=api_token.strip() if api_token else None,
		timeout_seconds=timeout_seconds,
	)



def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Reply and close feedback after approval.")
	parser.add_argument("--approval-text", required=True)
	parser.add_argument("--feedback-id", type=int, required=True)
	parser.add_argument("--reply-text")
	parser.add_argument("--reply-file", type=Path)
	parser.add_argument("--close", action="store_true", default=True)
	parser.add_argument("--preview-only", action="store_true")
	parser.add_argument("--timeout", type=float, default=20.0)
	return parser.parse_args()



def validate_approval(approval_text: str, feedback_id: int) -> None:
	match = APPROVAL_PATTERN.match(approval_text)
	if match is None:
		raise ReplyError("Approval text must match: 批准并执行 #ID")
	approved_id = int(match.group(1))
	if approved_id != feedback_id:
		raise ReplyError(
			f"Approval ID mismatch: approved #{approved_id}, expected #{feedback_id}",
		)



def load_reply_text(reply_text: str | None, reply_file: Path | None) -> str:
	if bool(reply_text) == bool(reply_file):
		raise ReplyError("Provide exactly one of --reply-text or --reply-file.")

	if reply_file is not None:
		if not reply_file.exists():
			raise ReplyError(f"Reply file does not exist: {reply_file}")
		text = reply_file.read_text(encoding="utf-8")
	else:
		text = reply_text or ""

	normalized = text.strip()
	if not normalized:
		raise ReplyError("Reply text cannot be empty.")
	return normalized



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
		raise ReplyError(f"API {method} {path} failed: HTTP {exc.code} {message}") from exc
	except error.URLError as exc:
		raise ReplyError(f"API {method} {path} failed: {exc.reason}") from exc

	if not raw:
		return None

	try:
		return json.loads(raw)
	except json.JSONDecodeError as exc:
		raise ReplyError(f"Invalid JSON from API {method} {path}: {raw[:200]}") from exc



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



def main() -> int:
	args = parse_args()
	try:
		validate_approval(args.approval_text, args.feedback_id)
		reply_message = load_reply_text(args.reply_text, args.reply_file)
		config = build_config(args.timeout)
	except ReplyError as exc:
		print(str(exc), file=sys.stderr)
		return 2

	payload = {
		"reply_message": reply_message,
		"close": bool(args.close),
	}

	if args.preview_only:
		print(
			json.dumps(
				{
					"feedback_id": args.feedback_id,
					"payload": payload,
				},
				ensure_ascii=False,
				indent=2,
			),
		)
		return 0

	opener = request.build_opener(request.HTTPCookieProcessor())
	try:
		login_admin(opener, config)
		response = api_request(
			opener,
			config,
			"POST",
			f"/api/admin/feedback/{args.feedback_id}/reply",
			payload,
		)
	except ReplyError as exc:
		print(str(exc), file=sys.stderr)
		return 1

	print(
		json.dumps(
			{
				"status": "replied",
				"feedback_id": args.feedback_id,
				"response": response,
			},
			ensure_ascii=False,
			indent=2,
		),
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

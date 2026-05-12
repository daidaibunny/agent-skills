#!/usr/bin/env python3
"""Daily API drift checker for contract-break risk detection."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib import error, request


@dataclass(frozen=True)
class Target:
	id: str
	name: str
	url: str
	method: str = "GET"
	headers: dict[str, str] | None = None
	body: dict[str, Any] | None = None
	use_admin_session: bool = False


@dataclass
class TargetResult:
	id: str
	name: str
	url: str
	ok: bool
	status_code: int | None
	error_message: str | None
	path_count: int
	signature_hash: str | None
	missing_paths: list[str]
	added_paths: list[str]
	risk_level: str  # none|medium|high
	risk_reason: str | None


def now_utc() -> datetime:
	return datetime.now(timezone.utc)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Check API drift and crash risk against previous signatures.",
	)
	parser.add_argument(
		"--env-file",
		default=".env.codex-feedback-automation.local",
		help="Project env file used for placeholder expansion.",
	)
	parser.add_argument(
		"--targets-file",
		default=str(Path(__file__).resolve().parents[1] / "references" / "targets.json"),
		help="JSON file that defines monitored APIs.",
	)
	parser.add_argument(
		"--state-file",
		default=".codex/api-drift/state.json",
		help="State file storing the previous successful signatures.",
	)
	parser.add_argument(
		"--report-dir",
		default=".codex/api-drift/reports",
		help="Directory to write markdown reports.",
	)
	parser.add_argument(
		"--latest-json",
		default=".codex/api-drift/latest.json",
		help="Path to write latest machine-readable run output.",
	)
	parser.add_argument(
		"--timeout-seconds",
		type=float,
		default=15.0,
		help="HTTP timeout for each API request.",
	)
	parser.add_argument(
		"--retries",
		type=int,
		default=1,
		help="Retry count for transient network failures.",
	)
	parser.add_argument(
		"--max-diff-lines",
		type=int,
		default=30,
		help="Max missing/added path lines recorded per target.",
	)
	parser.add_argument(
		"--allow-baseline-reset",
		action="store_true",
		help="When set, accept current contracts as fresh baseline (use carefully).",
	)
	parser.add_argument(
		"--retain-days",
		type=int,
		default=30,
		help="Delete report files older than this number of days. Set <=0 to disable.",
	)
	parser.add_argument(
		"--retain-count",
		type=int,
		default=90,
		help="Keep at most this number of newest report files. Set <=0 to disable.",
	)
	return parser.parse_args()


def load_env_file(env_path: Path) -> dict[str, str]:
	env: dict[str, str] = {}
	if not env_path.exists():
		return env

	for raw_line in env_path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		env[key.strip()] = value.strip().strip("'").strip('"')
	return env


def expand_placeholders(raw: str, env: dict[str, str]) -> str:
	result = raw
	for key, value in env.items():
		result = result.replace(f"${{{key}}}", value)
	result = result.replace("${NOW_UTC}", now_utc().isoformat())
	return result


def normalize_targets(payload: Any, env: dict[str, str]) -> list[Target]:
	if not isinstance(payload, list):
		raise ValueError("targets file must be a JSON array")

	targets: list[Target] = []
	for item in payload:
		if not isinstance(item, dict):
			continue
		target_id = str(item.get("id") or "").strip()
		name = str(item.get("name") or target_id).strip()
		enabled_if_env = str(item.get("enabled_if_env") or "").strip()
		if enabled_if_env and not str(env.get(enabled_if_env, "")).strip():
			continue
		url = expand_placeholders(str(item.get("url") or "").strip(), env)
		method = str(item.get("method") or "GET").upper()
		if "${" in url:
			continue
		if not target_id or not url:
			continue

		raw_headers = item.get("headers") if isinstance(item.get("headers"), dict) else {}
		headers: dict[str, str] = {}
		for header_key, header_value in raw_headers.items():
			expanded = expand_placeholders(str(header_value), env).strip()
			if expanded:
				headers[str(header_key)] = expanded

		body = item.get("body") if isinstance(item.get("body"), dict) else None
		targets.append(
			Target(
				id=target_id,
				name=name,
				url=url,
				method=method,
				headers=headers or None,
				body=body,
				use_admin_session=bool(item.get("use_admin_session", False)),
			),
		)

	return targets


def request_json(
	target: Target,
	timeout_seconds: float,
	*,
	opener: request.OpenerDirector | None = None,
	retries: int = 0,
) -> tuple[int | None, Any, str | None]:
	payload_bytes = None
	if target.body is not None:
		payload_bytes = json.dumps(target.body, ensure_ascii=False).encode("utf-8")
	headers = {"User-Agent": "codex-api-drift-guard/1.0"}
	if target.headers:
		headers.update(target.headers)
	if payload_bytes is not None and "Content-Type" not in headers:
		headers["Content-Type"] = "application/json"

	req = request.Request(
		url=target.url,
		method=target.method,
		data=payload_bytes,
		headers=headers,
	)
	attempt = 0
	while True:
		try:
			if opener is None:
				with request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
					status_code = getattr(resp, "status", None)
					raw_text = resp.read().decode("utf-8", errors="replace")
			else:
				with opener.open(req, timeout=timeout_seconds) as resp:  # noqa: S310
					status_code = getattr(resp, "status", None)
					raw_text = resp.read().decode("utf-8", errors="replace")
			break
		except error.HTTPError as exc:
			msg = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
			return exc.code, None, f"HTTP {exc.code}: {msg[:240]}"
		except error.URLError as exc:
			if attempt < retries:
				attempt += 1
				continue
			return None, None, f"Network error: {exc.reason}"
		except TimeoutError:
			if attempt < retries:
				attempt += 1
				continue
			return None, None, "Timeout"

	if not raw_text:
		return status_code, None, "Empty response"

	try:
		return status_code, json.loads(raw_text), None
	except json.JSONDecodeError:
		return status_code, None, "Response is not valid JSON"


def collect_paths(value: Any, prefix: str = "") -> set[str]:
	paths: set[str] = set()
	if isinstance(value, dict):
		for key in sorted(value.keys()):
			child_prefix = f"{prefix}.{key}" if prefix else str(key)
			paths.add(child_prefix)
			paths.update(collect_paths(value[key], child_prefix))
		return paths

	if isinstance(value, list):
		list_prefix = f"{prefix}[]" if prefix else "[]"
		paths.add(list_prefix)
		for item in value[:8]:
			paths.update(collect_paths(item, list_prefix))
		return paths

	type_name = type(value).__name__
	if prefix:
		paths.add(f"{prefix}::{type_name}")
	else:
		paths.add(f"::{type_name}")
	return paths


def compute_signature_hash(paths: set[str]) -> str:
	joined = "\n".join(sorted(paths))
	return sha256(joined.encode("utf-8")).hexdigest()


def risk_rank(level: str) -> int:
	if level == "high":
		return 2
	if level == "medium":
		return 1
	return 0


def normalize_alert_threshold(value: str) -> str:
	lower = value.strip().lower()
	if lower in {"none", "medium", "high"}:
		return lower
	return "high"


def summarize_highest_risk(results: list[TargetResult]) -> str:
	if any(item.risk_level == "high" for item in results):
		return "high"
	if any(item.risk_level == "medium" for item in results):
		return "medium"
	return "none"


def should_raise_alert(highest_risk: str, threshold: str) -> bool:
	return risk_rank(highest_risk) >= risk_rank(threshold)


def compute_alert_fingerprint(results: list[TargetResult], threshold: str) -> str:
	normalized = [
		{
			"id": item.id,
			"risk_level": item.risk_level,
			"risk_reason": item.risk_reason,
			"missing_paths": item.missing_paths,
			"added_paths": item.added_paths,
		}
		for item in sorted(results, key=lambda target_result: target_result.id)
		if risk_rank(item.risk_level) >= risk_rank(threshold)
	]
	return sha256(
		json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8"),
	).hexdigest()


def load_json(path: Path) -> Any:
	if not path.exists():
		return None
	return json.loads(path.read_text(encoding="utf-8"))


def ensure_parent(path: Path) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)


def build_result(
	target: Target,
	status_code: int | None,
	payload: Any,
	err: str | None,
	previous_paths: set[str] | None,
	max_diff_lines: int,
) -> TargetResult:
	if err is not None or payload is None:
		return TargetResult(
			id=target.id,
			name=target.name,
			url=target.url,
			ok=False,
			status_code=status_code,
			error_message=err or "Unknown error",
			path_count=0,
			signature_hash=None,
			missing_paths=[],
			added_paths=[],
			risk_level="high",
			risk_reason="endpoint_unreachable_or_invalid_json",
		)

	current_paths = collect_paths(payload)
	current_hash = compute_signature_hash(current_paths)
	if previous_paths is None:
		return TargetResult(
			id=target.id,
			name=target.name,
			url=target.url,
			ok=True,
			status_code=status_code,
			error_message=None,
			path_count=len(current_paths),
			signature_hash=current_hash,
			missing_paths=[],
			added_paths=[],
			risk_level="none",
			risk_reason="baseline_initialized",
		)

	missing = sorted(previous_paths - current_paths)
	added = sorted(current_paths - previous_paths)
	if missing:
		return TargetResult(
			id=target.id,
			name=target.name,
			url=target.url,
			ok=True,
			status_code=status_code,
			error_message=None,
			path_count=len(current_paths),
			signature_hash=current_hash,
			missing_paths=missing[:max_diff_lines],
			added_paths=added[:max_diff_lines],
			risk_level="high",
			risk_reason="required_contract_paths_missing",
		)
	if added:
		return TargetResult(
			id=target.id,
			name=target.name,
			url=target.url,
			ok=True,
			status_code=status_code,
			error_message=None,
			path_count=len(current_paths),
			signature_hash=current_hash,
			missing_paths=[],
			added_paths=added[:max_diff_lines],
			risk_level="medium",
			risk_reason="new_contract_paths_detected",
		)

	return TargetResult(
		id=target.id,
		name=target.name,
		url=target.url,
		ok=True,
		status_code=status_code,
		error_message=None,
		path_count=len(current_paths),
		signature_hash=current_hash,
		missing_paths=[],
		added_paths=[],
		risk_level="none",
		risk_reason=None,
	)


def login_feedback_admin(
	opener: request.OpenerDirector,
	env: dict[str, str],
	timeout_seconds: float,
) -> str | None:
	base_url = str(env.get("FEEDBACK_API_BASE_URL", "")).strip().rstrip("/")
	admin_user = str(env.get("FEEDBACK_ADMIN_USER", "")).strip()
	admin_password = str(env.get("FEEDBACK_ADMIN_PASSWORD", "")).strip()
	if not base_url or not admin_user or not admin_password:
		return "Missing FEEDBACK_API_BASE_URL/FEEDBACK_ADMIN_USER/FEEDBACK_ADMIN_PASSWORD"

	api_token = str(env.get("FEEDBACK_API_TOKEN", "")).strip()
	headers = {
		"User-Agent": "codex-api-drift-guard/1.0",
		"Content-Type": "application/json",
	}
	if api_token:
		headers["X-API-Key"] = api_token

	req = request.Request(
		url=f"{base_url}/api/auth/login",
		method="POST",
		data=json.dumps(
			{
				"user_id": admin_user,
				"password": admin_password,
			},
			ensure_ascii=False,
		).encode("utf-8"),
		headers=headers,
	)
	try:
		with opener.open(req, timeout=timeout_seconds):  # noqa: S310
			return None
	except error.HTTPError as exc:
		message = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
		return f"Admin login failed: HTTP {exc.code}: {message[:240]}"
	except error.URLError as exc:
		return f"Admin login failed: {exc.reason}"
	except TimeoutError:
		return "Admin login timeout"


def write_markdown_report(path: Path, run_at: datetime, results: list[TargetResult]) -> None:
	high = [item for item in results if item.risk_level == "high"]
	medium = [item for item in results if item.risk_level == "medium"]
	lines: list[str] = []
	lines.append("# API Drift Daily Report")
	lines.append("")
	lines.append(f"- Run at (UTC): `{run_at.isoformat()}`")
	lines.append(f"- High risk: `{len(high)}`")
	lines.append(f"- Medium risk: `{len(medium)}`")
	lines.append(f"- Healthy: `{len([item for item in results if item.risk_level == 'none'])}`")
	lines.append("")
	lines.append("## Target Summary")
	lines.append("")
	for item in results:
		status = "OK" if item.ok else "FAIL"
		lines.append(
			(
				f"- `{item.id}` ({item.name}): {status}, risk={item.risk_level}, "
				f"http={item.status_code}, paths={item.path_count}"
			),
		)
		if item.error_message:
			lines.append(f"  - error: `{item.error_message}`")
		if item.missing_paths:
			lines.append("  - missing paths:")
			for path_item in item.missing_paths:
				lines.append(f"    - `{path_item}`")
		if item.added_paths:
			lines.append("  - added paths:")
			for path_item in item.added_paths:
				lines.append(f"    - `{path_item}`")
	lines.append("")
	lines.append("## Action")
	lines.append("")
	lines.append("- If any `high` risk exists: treat as potential future crash and patch adapters first.")
	lines.append("- If only `medium` risk exists: verify parser compatibility before next release.")
	lines.append("- If all healthy: keep baseline and continue daily checks.")

	ensure_parent(path)
	path.write_text("\n".join(lines), encoding="utf-8")


def cleanup_report_files(
	report_dir: Path,
	*,
	retain_days: int,
	retain_count: int,
) -> dict[str, int]:
	removed_by_days = 0
	removed_by_count = 0
	if not report_dir.exists():
		return {"removed_by_days": 0, "removed_by_count": 0}

	report_files = sorted(
		(
			path
			for path in report_dir.glob("api-drift-*.md")
			if path.is_file()
		),
		key=lambda item: item.stat().st_mtime,
	)
	if not report_files:
		return {"removed_by_days": 0, "removed_by_count": 0}

	if retain_days > 0:
		cutoff = now_utc() - timedelta(days=retain_days)
		kept_files: list[Path] = []
		for report_file in report_files:
			mtime = datetime.fromtimestamp(report_file.stat().st_mtime, tz=timezone.utc)
			if mtime < cutoff:
				report_file.unlink(missing_ok=True)
				removed_by_days += 1
			else:
				kept_files.append(report_file)
		report_files = kept_files

	if retain_count > 0 and len(report_files) > retain_count:
		excess = len(report_files) - retain_count
		for report_file in report_files[:excess]:
			report_file.unlink(missing_ok=True)
			removed_by_count += 1

	return {
		"removed_by_days": removed_by_days,
		"removed_by_count": removed_by_count,
	}


def main() -> int:
	args = parse_args()
	run_at = now_utc()

	env = dict(os.environ)
	env.update(load_env_file(Path(args.env_file)))

	targets_payload = load_json(Path(args.targets_file))
	if targets_payload is None:
		print(f"targets file not found: {args.targets_file}")
		return 2

	targets = normalize_targets(targets_payload, env)
	if not targets:
		print("no valid targets configured")
		return 2

	admin_session_opener: request.OpenerDirector | None = None
	if any(target.use_admin_session for target in targets):
		admin_session_opener = request.build_opener(request.HTTPCookieProcessor())
		login_error = login_feedback_admin(admin_session_opener, env, args.timeout_seconds)
		if login_error:
			results = [
				TargetResult(
					id=target.id,
					name=target.name,
					url=target.url,
					ok=False,
					status_code=None,
					error_message=login_error,
					path_count=0,
					signature_hash=None,
					missing_paths=[],
					added_paths=[],
					risk_level="high",
					risk_reason="admin_login_failed",
				)
				for target in targets
				if target.use_admin_session
			]
			run_at = now_utc()
			report_dir = Path(args.report_dir)
			report_name = f"api-drift-{run_at.strftime('%Y%m%d-%H%M%S')}.md"
			report_path = report_dir / report_name
			write_markdown_report(report_path, run_at, results)
			cleanup_summary = cleanup_report_files(
				report_dir,
				retain_days=args.retain_days,
				retain_count=args.retain_count,
			)
			latest_payload = {
				"run_at": run_at.isoformat(),
				"report_path": str(report_path),
				"state_path": str(Path(args.state_file)),
				"summary": {"high": len(results), "medium": 0, "none": 0},
				"cleanup": cleanup_summary,
				"results": [
					{
						"id": item.id,
						"name": item.name,
						"url": item.url,
						"ok": item.ok,
						"status_code": item.status_code,
						"error_message": item.error_message,
						"path_count": item.path_count,
						"risk_level": item.risk_level,
						"risk_reason": item.risk_reason,
						"missing_paths": item.missing_paths,
						"added_paths": item.added_paths,
					}
					for item in results
				],
			}
			latest_path = Path(args.latest_json)
			ensure_parent(latest_path)
			latest_path.write_text(
				json.dumps(latest_payload, ensure_ascii=False, indent=2),
				encoding="utf-8",
			)
			print(json.dumps(latest_payload, ensure_ascii=False, indent=2))
			return 1

	state_path = Path(args.state_file)
	previous_state = load_json(state_path) or {}
	previous_targets = (
		previous_state.get("targets")
		if isinstance(previous_state, dict)
		else {}
	)
	if not isinstance(previous_targets, dict):
		previous_targets = {}
	previous_alert = (
		previous_state.get("alert")
		if isinstance(previous_state, dict)
		else {}
	)
	if not isinstance(previous_alert, dict):
		previous_alert = {}

	results: list[TargetResult] = []
	next_targets_state: dict[str, Any] = dict(previous_targets)

	for target in targets:
		previous_item = previous_targets.get(target.id)
		previous_paths = None
		if isinstance(previous_item, dict) and isinstance(previous_item.get("paths"), list):
			previous_paths = set(str(item) for item in previous_item.get("paths", []))

		target_opener = admin_session_opener if target.use_admin_session else None
		status_code, payload, err = request_json(
			target,
			args.timeout_seconds,
			opener=target_opener,
			retries=max(args.retries, 0),
		)
		result = build_result(
			target,
			status_code,
			payload,
			err,
			previous_paths=previous_paths,
			max_diff_lines=args.max_diff_lines,
		)
		results.append(result)

		if not result.ok:
			continue

		if result.signature_hash is None:
			continue

		current_paths = sorted(collect_paths(payload))
		should_write_current = True
		if result.risk_level == "high" and not args.allow_baseline_reset:
			should_write_current = False

		if previous_paths is None:
			should_write_current = True

		if should_write_current:
			next_targets_state[target.id] = {
				"name": target.name,
				"url": target.url,
				"paths": current_paths,
				"signature_hash": result.signature_hash,
				"last_success_at": run_at.isoformat(),
			}

	summary = {
		"high": len([item for item in results if item.risk_level == "high"]),
		"medium": len([item for item in results if item.risk_level == "medium"]),
		"none": len([item for item in results if item.risk_level == "none"]),
	}
	highest_risk = summarize_highest_risk(results)
	alert_threshold = normalize_alert_threshold(
		str(env.get("API_DRIFT_ALERT_THRESHOLD", "high")),
	)
	alert_needed = should_raise_alert(highest_risk, alert_threshold)
	alert_fingerprint = (
		compute_alert_fingerprint(results, alert_threshold)
		if alert_needed
		else ""
	)
	previous_alert_fingerprint = str(previous_alert.get("last_fingerprint", "")).strip()
	alert_is_new = bool(alert_needed and alert_fingerprint != previous_alert_fingerprint)

	alert_state = dict(previous_alert)
	alert_state.update(
		{
			"last_checked_at": run_at.isoformat(),
			"threshold": alert_threshold,
			"last_highest_risk": highest_risk,
		},
	)
	if alert_needed:
		alert_state.update(
			{
				"last_triggered_at": run_at.isoformat(),
				"last_fingerprint": alert_fingerprint,
				"last_new_alert_at": run_at.isoformat() if alert_is_new else previous_alert.get("last_new_alert_at"),
			},
		)

	state_payload = {
		"updated_at": run_at.isoformat(),
		"targets": next_targets_state,
		"alert": alert_state,
	}
	ensure_parent(state_path)
	state_path.write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")

	report_dir = Path(args.report_dir)
	report_name = f"api-drift-{run_at.strftime('%Y%m%d-%H%M%S')}.md"
	report_path = report_dir / report_name
	write_markdown_report(report_path, run_at, results)
	cleanup_summary = cleanup_report_files(
		report_dir,
		retain_days=args.retain_days,
		retain_count=args.retain_count,
	)

	latest_payload = {
		"run_at": run_at.isoformat(),
		"report_path": str(report_path),
		"state_path": str(state_path),
		"summary": summary,
		"cleanup": cleanup_summary,
		"alert": {
			"threshold": alert_threshold,
			"highest_risk": highest_risk,
			"needed": alert_needed,
			"is_new": alert_is_new,
			"fingerprint": alert_fingerprint,
			"notification_channel": "admin-feedback-message",
		},
		"results": [
			{
				"id": item.id,
				"name": item.name,
				"url": item.url,
				"ok": item.ok,
				"status_code": item.status_code,
				"error_message": item.error_message,
				"path_count": item.path_count,
				"risk_level": item.risk_level,
				"risk_reason": item.risk_reason,
				"missing_paths": item.missing_paths,
				"added_paths": item.added_paths,
			}
			for item in results
		],
	}
	latest_path = Path(args.latest_json)
	ensure_parent(latest_path)
	latest_path.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

	print(json.dumps(latest_payload, ensure_ascii=False, indent=2))
	exit_nonzero_on_alert = str(
		env.get("API_DRIFT_EXIT_NONZERO_ON_ALERT", "1"),
	).strip().lower() not in {"0", "false", "no", "off"}
	if alert_needed and exit_nonzero_on_alert:
		return 3
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

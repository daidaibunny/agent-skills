#!/usr/bin/env python3
"""Execute approved feedback changes with test and git safeguards."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


APPROVAL_PATTERN = re.compile(r"^\s*批准并执行\s*#(\d+)\s*$")


@dataclass(frozen=True)
class ExecutionConfig:
	feedback_id: int
	approval_text: str
	workdir: Path
	apply_cmd: str
	test_cmds: list[str]
	commit_message: str
	push: bool
	branch_date: str
	push_script: Path
	dry_run: bool


class ExecutionError(RuntimeError):
	"""Raised when the execution pipeline cannot continue."""



def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Execute approved feedback code changes.")
	parser.add_argument("--approval-text", required=True)
	parser.add_argument("--feedback-id", type=int, required=True)
	parser.add_argument("--workdir", type=Path, required=True)
	parser.add_argument("--apply-cmd", required=True)
	parser.add_argument("--test-cmd", action="append", dest="test_cmds", default=[])
	parser.add_argument("--commit-message", required=True)
	parser.add_argument("--push", action="store_true")
	parser.add_argument("--branch-date", default=datetime.now().strftime("%Y%m%d"))
	parser.add_argument(
		"--push-script",
		type=Path,
		default=Path(__file__).resolve().parent / "push_with_proxy.sh",
	)
	parser.add_argument("--dry-run", action="store_true")
	return parser.parse_args()



def build_config(args: argparse.Namespace) -> ExecutionConfig:
	if not args.test_cmds:
		raise ExecutionError("At least one --test-cmd is required.")
	if not args.workdir.exists():
		raise ExecutionError(f"Workdir does not exist: {args.workdir}")
	if not args.push_script.exists():
		raise ExecutionError(f"Push script does not exist: {args.push_script}")
	return ExecutionConfig(
		feedback_id=args.feedback_id,
		approval_text=args.approval_text,
		workdir=args.workdir.resolve(),
		apply_cmd=args.apply_cmd,
		test_cmds=list(args.test_cmds),
		commit_message=args.commit_message,
		push=args.push,
		branch_date=args.branch_date,
		push_script=args.push_script.resolve(),
		dry_run=args.dry_run,
	)



def validate_approval(approval_text: str, feedback_id: int) -> None:
	match = APPROVAL_PATTERN.match(approval_text)
	if match is None:
		raise ExecutionError("Approval text must match: 批准并执行 #ID")
	approved_id = int(match.group(1))
	if approved_id != feedback_id:
		raise ExecutionError(
			f"Approval ID mismatch: approved #{approved_id}, expected #{feedback_id}",
		)



def run_command(command: str, cwd: Path, dry_run: bool) -> None:
	if dry_run:
		print(f"[dry-run] {command}")
		return
	result = subprocess.run(command, cwd=str(cwd), shell=True)
	if result.returncode != 0:
		raise ExecutionError(f"Command failed ({result.returncode}): {command}")



def run_capture(command: list[str], cwd: Path) -> str:
	result = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True)
	if result.returncode != 0:
		raise ExecutionError(
			f"Command failed ({result.returncode}): {' '.join(command)}\n{result.stderr.strip()}",
		)
	return result.stdout.strip()



def ensure_branch(config: ExecutionConfig, branch_name: str) -> None:
	current_branch = run_capture(["git", "branch", "--show-current"], config.workdir)
	if current_branch == branch_name:
		return
	branches = run_capture(["git", "branch", "--list", branch_name], config.workdir)
	if branches:
		run_command(f"git checkout {branch_name}", config.workdir, config.dry_run)
		return
	run_command(f"git checkout -b {branch_name}", config.workdir, config.dry_run)



def has_changes(workdir: Path) -> bool:
	output = run_capture(["git", "status", "--porcelain"], workdir)
	return bool(output)



def execute(config: ExecutionConfig) -> dict[str, str | int | bool]:
	validate_approval(config.approval_text, config.feedback_id)
	branch_name = f"codex/feedback-fix-{config.feedback_id}-{config.branch_date}"
	ensure_branch(config, branch_name)

	run_command(config.apply_cmd, config.workdir, config.dry_run)
	for test_cmd in config.test_cmds:
		run_command(test_cmd, config.workdir, config.dry_run)

	if not config.dry_run and not has_changes(config.workdir):
		raise ExecutionError("No file changes detected after apply/test stage.")

	run_command("git add .", config.workdir, config.dry_run)
	run_command(f"git commit -m \"{config.commit_message}\"", config.workdir, config.dry_run)

	if config.push:
		run_command(f"bash {config.push_script} {config.workdir}", config.workdir, config.dry_run)

	return {
		"feedback_id": config.feedback_id,
		"branch": branch_name,
		"pushed": config.push,
		"dry_run": config.dry_run,
	}



def main() -> int:
	try:
		config = build_config(parse_args())
		result = execute(config)
	except ExecutionError as exc:
		print(str(exc), file=sys.stderr)
		return 1

	print(json.dumps(result, ensure_ascii=False, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

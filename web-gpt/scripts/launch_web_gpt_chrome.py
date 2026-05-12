#!/usr/bin/env python3
"""Launch an isolated Chrome instance for the web-gpt skill."""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

from cdp_client import CdpError, ensure_cdp_available


DEFAULT_PROJECT_URL = (
	"https://chatgpt.com/g/g-p-69e8a817b614819181a4aa9f6f2c6f80-bdi-agent/project"
)
DEFAULT_PROFILE_DIR = Path.home() / ".codex" / "web-gpt-chrome-profile"
DEFAULT_PORT = 9222


def launch_chrome(profile_dir: Path, port: int, initial_url: str) -> None:
	profile_dir.mkdir(parents=True, exist_ok=True)
	command = [
		"open",
		"-na",
		"Google Chrome",
		"--args",
		f"--user-data-dir={profile_dir}",
		f"--remote-debugging-port={port}",
		f"--remote-allow-origins=http://127.0.0.1:{port}",
		"--no-first-run",
		"--no-default-browser-check",
		initial_url,
	]
	subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Launch the isolated web-gpt Chrome instance.")
	parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
	parser.add_argument("--port", type=int, default=DEFAULT_PORT)
	parser.add_argument("--url", default=DEFAULT_PROJECT_URL)
	parser.add_argument("--wait-seconds", type=float, default=20.0)
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	profile_dir = Path(args.profile_dir).expanduser()
	launch_chrome(profile_dir, args.port, args.url)
	deadline = time.monotonic() + args.wait_seconds
	last_error: Exception | None = None
	while time.monotonic() < deadline:
		try:
			version = ensure_cdp_available(f"http://127.0.0.1:{args.port}")
			print(f"web-gpt Chrome ready: {version.get('Browser', 'Chrome')}")
			print(f"profile_dir={profile_dir}")
			print(f"cdp_url=http://127.0.0.1:{args.port}")
			return 0
		except CdpError as exc:
			last_error = exc
			time.sleep(1)
	print(f"Chrome launched but DevTools endpoint was not ready: {last_error}")
	return 1


if __name__ == "__main__":
	raise SystemExit(main())

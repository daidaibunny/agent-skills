"""Small Chrome DevTools Protocol helpers for the web-gpt skill."""

from __future__ import annotations

import json
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import requests
import websocket


DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class CdpError(RuntimeError):
	"""Raised when Chrome DevTools Protocol operations fail."""


@dataclass(frozen=True)
class CdpTarget:
	id: str
	url: str
	title: str
	websocket_url: str


def ensure_cdp_available(cdp_url: str = DEFAULT_CDP_URL) -> dict[str, Any]:
	try:
		response = requests.get(f"{cdp_url}/json/version", timeout=5)
	except requests.RequestException as exc:
		raise CdpError(
			f"Chrome DevTools endpoint is not available at {cdp_url}. "
			"Restart Chrome with --remote-debugging-port=9222.",
		) from exc
	if response.status_code != 200:
		raise CdpError(f"Unexpected DevTools version status {response.status_code}: {response.text}")
	return response.json()


def list_targets(cdp_url: str = DEFAULT_CDP_URL) -> list[CdpTarget]:
	ensure_cdp_available(cdp_url)
	response = requests.get(f"{cdp_url}/json/list", timeout=10)
	response.raise_for_status()
	targets: list[CdpTarget] = []
	for item in response.json():
		if item.get("type") != "page":
			continue
		websocket_url = item.get("webSocketDebuggerUrl")
		if not websocket_url:
			continue
		targets.append(
			CdpTarget(
				id=str(item.get("id") or ""),
				url=str(item.get("url") or ""),
				title=str(item.get("title") or ""),
				websocket_url=str(websocket_url),
			),
		)
	return targets


def create_target(url: str, cdp_url: str = DEFAULT_CDP_URL) -> CdpTarget:
	ensure_cdp_available(cdp_url)
	response = requests.put(f"{cdp_url}/json/new", timeout=10)
	if response.status_code == 405:
		response = requests.get(f"{cdp_url}/json/new", timeout=10)
	response.raise_for_status()
	item = response.json()
	target_id = str(item.get("id") or "")
	deadline = time.monotonic() + 15
	target: CdpTarget | None = None
	while time.monotonic() < deadline:
		for target in list_targets(cdp_url):
			if target.id == target_id and target.websocket_url:
				break
		if target and target.id == target_id:
			break
		time.sleep(0.5)
	if target and target.id == target_id:
		session = CdpSession(target)
		try:
			session.command("Page.enable")
			session.command("Page.navigate", {"url": url})
		finally:
			session.close()
		return CdpTarget(
			id=target.id,
			url=url,
			title=target.title,
			websocket_url=target.websocket_url,
		)
	websocket_url = item.get("webSocketDebuggerUrl")
	if not websocket_url:
		raise CdpError(f"Created target has no websocket URL: {item}")
	return CdpTarget(
		id=target_id,
		url=str(item.get("url") or url),
		title=str(item.get("title") or ""),
		websocket_url=str(websocket_url),
	)


def navigate_target(target: CdpTarget, url: str) -> CdpTarget:
	session = CdpSession(target)
	try:
		session.command("Page.enable")
		session.command("Page.navigate", {"url": url})
	finally:
		session.close()
	return CdpTarget(
		id=target.id,
		url=url,
		title=target.title,
		websocket_url=target.websocket_url,
	)


class CdpSession:
	def __init__(self, target: CdpTarget):
		self.target = target
		self._next_id = 1
		self._ws = websocket.create_connection(target.websocket_url, timeout=30)

	def close(self) -> None:
		self._ws.close()

	def command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
		command_id = self._next_id
		self._next_id += 1
		self._ws.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
		while True:
			message = json.loads(self._ws.recv())
			if message.get("id") != command_id:
				continue
			if "error" in message:
				raise CdpError(f"{method} failed: {message['error']}")
			return message.get("result", {})

	def evaluate(self, expression: str, *, timeout_seconds: float = 30.0) -> Any:
		old_timeout = self._ws.gettimeout()
		self._ws.settimeout(timeout_seconds)
		try:
			result = self.command(
				"Runtime.evaluate",
				{
					"expression": expression,
					"awaitPromise": True,
					"returnByValue": True,
					"userGesture": True,
				},
			)
		finally:
			self._ws.settimeout(old_timeout)
		if "exceptionDetails" in result:
			raise CdpError(f"JavaScript evaluation failed: {result['exceptionDetails']}")
		remote_result = result.get("result", {})
		if "value" in remote_result:
			return remote_result["value"]
		if remote_result.get("type") == "undefined":
			return None
		return remote_result


def evaluate(target: CdpTarget, expression: str, *, timeout_seconds: float = 30.0) -> Any:
	session = CdpSession(target)
	try:
		return session.evaluate(expression, timeout_seconds=timeout_seconds)
	finally:
		session.close()


def wait_for_ready_state(
	target: CdpTarget,
	*,
	timeout_seconds: float = 90.0,
	poll_seconds: float = 1.0,
) -> None:
	deadline = time.monotonic() + timeout_seconds
	while time.monotonic() < deadline:
		try:
			state = evaluate(target, "document.readyState", timeout_seconds=5)
			if state in {"interactive", "complete"}:
				return
		except CdpError:
			pass
		time.sleep(poll_seconds)
	raise CdpError(f"Timed out waiting for page readiness: {target.url}")

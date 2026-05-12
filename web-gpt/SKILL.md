---
name: web-gpt
description: Use an isolated, already-authenticated ChatGPT web UI browser instance to run prompt batches through one project tab, creating one new project chat per prompt, waiting for complete responses, and exporting visible responses without using the API.
---

# Web GPT

Use this skill only when the user explicitly asks to drive the ChatGPT web interface instead of an application programming interface.

## Boundaries

- Use only an already-authenticated browser session.
- Do not enter passwords, one-time codes, payment data, or solve captchas.
- Do not bypass browser, account, paywall, or platform safety barriers.
- Do not use this for formal benchmark runs; use the application programming interface for reproducible experiments.
- Do not hide automation, spoof fingerprints, alter transport fingerprints, bypass detection, or bypass platform controls.
- Treat the web user interface as best-effort: page layout, model picker, and response extraction can change.

## Required Setup

- Use the isolated `web-gpt` Chrome instance, not the user's main browser.
- Launch it with:

```bash
python /Users/lyw/.codex/skills/web-gpt/scripts/launch_web_gpt_chrome.py
```

- The isolated instance uses:
	- profile directory: `/Users/lyw/.codex/web-gpt-chrome-profile`,
	- local DevTools endpoint: `http://127.0.0.1:9222`,
	- `--remote-allow-origins=http://127.0.0.1:9222` so the local client can connect to the local DevTools endpoint,
	- the same normal Chrome engine and settings, with no fingerprint spoofing or anti-detection changes.
- The user must log in to ChatGPT once inside this isolated browser window if it is not already authenticated.
- Open the required ChatGPT project, not the root ChatGPT home page.
- For the current project, use `https://chatgpt.com/g/g-p-69e8a817b614819181a4aa9f6f2c6f80-bdi-agent/project`.
- If a prompt should be prefilled, append `?prompt=<url-encoded prompt>` to the project URL.
- Do not use `https://chatgpt.com/?prompt=...` unless the user explicitly asks for a non-project chat.
- Before batch prompts, configure and verify the project chat defaults in the web user interface:
	- Open the model selector and verify the checked model family is `Pro` for the current GPT Pro model tier.
	- Open the prompt-box thinking-strength selector and verify `进阶专业` is displayed, with `进阶` checked in the menu.
	- If either selector is not in the required state, set it before sending prompts.
	- If the exact model label is hidden by the web user interface, record the visible checked label instead of guessing.

## Batch Prompt Workflow

Use `scripts/run_chatgpt_project_prompt_batch_cdp.py` for stable project-scoped prompt batches.
The runner uses one isolated Chrome window and one browser tab. For each prompt, it opens a fresh
`BDI_Agent` project chat in that same tab, sends the prompt, waits until the reply is complete and
written to disk, then reuses the same tab for the next fresh project chat.

Prompt file formats:

- `.txt`: one prompt per non-empty line.
- `.json`: either a list of strings, a list of `{ "id": "...", "prompt": "..." }`, or `{ "prompts": [...] }`.
- `.jsonl`: one string or object per line.

Canonical batch run:

```bash
python /Users/lyw/.codex/skills/web-gpt/scripts/run_chatgpt_project_prompt_batch_cdp.py \
	--prompt-file /absolute/path/prompts.json \
	--output-dir /absolute/path/web_gpt_runs \
	--timeout-seconds 1800 \
	--settle-seconds 20
```

The batch runner:

- uses one isolated Chrome window and one tab for the whole run,
- creates a fresh `BDI_Agent` project chat for each prompt in that same tab,
- starts the next prompt only after the previous prompt reaches a complete, stable result,
- does not expose any multi-tab, concurrency, or separate-chat mode,
- records a `run_id`, manifest, prompt status, chat URL, timestamps, failures, and per-prompt JSON,
- waits for completion before accepting a result:
	- no visible stop-generation control,
	- no streaming or busy marker,
	- message text is stable for a settle window,
	- any visible `Continue generating` / `继续生成` control has been clicked and re-waited.
- writes UTF-8 JSON with `schema_version` and deterministic keys to avoid formatting loss.
- returns non-zero if any prompt fails, while preserving partial outputs.
- controls only the isolated Chrome instance via the local DevTools endpoint.

If login, captcha, account confirmation, or model-tier unavailability appears, stop and ask the user to take over.

## Exporting Completed Responses

Use `scripts/export_chatgpt_project_chats_cdp.py` to wait for already-open isolated project chats and export visible
messages to a specified file.

Canonical JSON export:

```bash
python /Users/lyw/.codex/skills/web-gpt/scripts/export_chatgpt_project_chats_cdp.py \
	--output /absolute/path/chatgpt_project_export.json \
	--timeout-seconds 1200 \
	--settle-seconds 20 \
	--fail-on-incomplete
```

The script:

- uses the already-authenticated isolated Chrome session,
- selects only tabs whose URL contains the current `BDI_Agent` project identifier,
- waits until generation controls disappear and message text remains stable,
- clicks visible `Continue generating` / `继续生成` controls by default,
- writes UTF-8 JSON with `schema_version`, completion metadata, per-tab messages, and hashes,
- exits non-zero with a partial export if `--fail-on-incomplete` is set and completion cannot be verified.

## Preferred Tooling

- Prefer the isolated DevTools-based scripts for repeatable batches.
- Use Computer Use only for one-time user-visible setup, such as login or verifying model settings.
- Do not manipulate the user's main Chrome while a `web-gpt` batch is running.
- Legacy AppleScript scripts are retained only as fallback utilities; do not use them as the default path.

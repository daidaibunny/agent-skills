# Agent Skills

Reusable agent skills library for Codex, Opencode, and Hermes agents.

## Structure

Each skill is a directory containing at minimum a `SKILL.md` file with YAML
frontmatter (name and description) followed by markdown instructions.

```
skill-name/
├── SKILL.md           # Main instructions (required)
├── scripts/           # Utility scripts (optional)
├── agents/            # Agent-specific config (optional)
├── references/        # Supplementary docs (optional)
└── assets/            # Bundled resources (optional)
```

## Installation

Clone this repository and copy skills to your agent's skills directory:

```bash
git clone https://github.com/daidaibunny/agent-skills.git
cp -r agent-skills/* ~/.codex/skills/
```

## Usage

Skills are surfaced in the agent's system prompt via their `description` field.
The agent reads descriptions and decides which skill to load based on the
user's request.

## Inventory

57 skills across multiple categories. See each `SKILL.md` for details.

# AGENTS.md — entry point for AI assistants working in this repo

This file is the portable, tool-agnostic entry point for any AI agent (Claude Code, Hermes/JARVIS,
or any model) working on CYM. It is tracked in the repo so it travels to every tool and machine —
unlike `CLAUDE.md` and `~/.claude/commands/dev.md`, which are local-only and do not propagate.

## Read first — the authoritative development workflow

**`.claude/rules/cym-canonical-workflow.md`** is the single source of truth for the development
lifecycle: versioning, release vs experimental boards, the multi-board build gate, commits,
branch/release authorization, authorship & contributor credit, AI attribution, hardware-test
evidence, releases & SD assets, model routing, and memory. If any other document disagrees with it,
the canonical workflow wins.

## Supporting rules (`.claude/rules/`)

- `cym-release-workflow.md` — exact multi-board build/version/release commands and SD-asset refresh.
- `cym-shared-codebase-multiboard-build.md` — which boards compile which shared source.
- `cym-dev-workflow.md` — task scoping and model-agnostic cost tier.
- `cym-contributor-attribution.md` — @birolt29 co-developer credit; handle/noreply privacy.
- `cym-lvgl-text-rules.md`, `cym-screen-stop-hooks.md`, `cym-webflasher-serial.md`,
  `cym-landscape-support.md`, `cym-memory-discipline.md` — domain-specific rules.

## Other anchors

- **Backlog:** `BACKLOG.md` (repo root) is the canonical backlog. There is no HERMES.md.
- **Project architecture / hardware:** `CLAUDE.md` (local, not tracked) holds detailed architecture
  notes; the binding *rules* live in `.claude/rules/`.

# CYM Canonical Development Workflow (authoritative)

This is the single source of truth for the CYM development lifecycle, intended to be followed
consistently by Claude Code, Hermes/JARVIS, and any model. It is **tracked in the repo** on
purpose — `CLAUDE.md` and `~/.claude/commands/dev.md` are local-only and do NOT travel to other
tools/machines, so the binding rules live here and in the other `.claude/rules/*.md` files.

Reconciled and confirmed by Jim 2026-09-24. Where a detailed rule file exists, it governs the
specifics; this file states the rule and points to it. If any older doc disagrees with this file,
this file wins.

---

## 1. Versioning within a cycle
Bump the PATCH digit (`Z`) in the SoC's `CMakeLists.txt` before any build that changes a binary.
MINOR/MAJOR only with explicit user approval. Version bump is manual (not automated by build.sh).

## 2. One version per cycle across boards  *(USER-CONFIRMED)*
All **release** boards built in a development cycle share the **same** version. Do NOT bump the
version separately per board. This supersedes any older "each board gets its own version bump /
no two binaries may share a version" wording (previously in cym-release-workflow.md, dev.md,
Makefile, commit_format_rule.md — all corrected).

## 3. Skipped boards & drift
A release board deliberately skipped in a cycle stays at its prior version. On drift, bring all
release boards to `max_current + 1` in the next cycle. For current versions, read each board's
`CMakeLists.txt` — never a hardcoded number in docs.

## 4. Release boards vs experimental  *(USER-CONFIRMED)*
- **Release boards (3):** NM-CYD-C5, WS-C5-28 (`ESP32C5/`), CYD-2432S028 (`ESP32/`). Version-synced,
  must build clean for shared-source changes, shipped in release assets + manifests + web flasher.
- **Experimental / bring-up:** Hosyond S3 (`ESP32S3/`). Currently a ~372-line bring-up stub with
  its own `main.c` (NOT the CYM app). Not version-synced, not shipped. Promotion to a release board
  is a backlog goal gated on actually porting CYM to ESP32-S3 (BACKLOG.md).

## 5. Shared-code build scope
A change to source compiled by multiple boards (esp. `ESP32C5/main/main.c`, shared components) must
build clean on every **release** board whose `CMakeLists.txt` compiles it (main.c ⇒ all 3).
ESP32S3 compiles its own stub `main.c`, so it is a compile canary only, not bound by this rule yet.
Details: `cym-shared-codebase-multiboard-build.md`.

## 6. Artifacts & packaging
Per-board binary set in `ESP32C5/binaries-esp32c5/`, `ESP32C5/binaries-ws-c5-28/`,
`ESP32/binaries-cyd-2432s028/`; per-board manifest JSON. Copy-to-export + `-full.bin` merge is
**automated** by the CMake POST_BUILD hook; version/manifest edits are manual. Details:
`cym-release-workflow.md`.

## 7. Commits
Subject = `vX.Y.Z: type(scope): description` (**version first**). Docs-only commits may omit the
version prefix (`type(scope): ...`). Stage board-specific files explicitly (never `git add -A`),
one logical change per commit. **Push `origin Jimgat_Dev` immediately after every commit.**
Details: `commit_format_rule` memory + `cym-release-workflow.md`.

## 8. Branch & release authorization  *(enforced)*
Work on `Jimgat_Dev`. Merge to `main`, tag, or `gh release` ONLY on explicit user request. The
harness soft-denies `git push * main *` and `gh release create *`; force-push and `idf.py flash`
are denied outright.

## 9. Authorship & contributor credit
Default author `JimGat`. @birolt29's patches are authored **as him** (handle +
`birolt29@users.noreply.github.com`, NEVER his real name/email) and he is credited **co-developer**.
Other external contributors' own work is authored via their GitHub noreply address and credited in
README. Committer stays Jim. Details: `cym-contributor-attribution.md`.

## 10. AI attribution
`Co-Authored-By:` must name the **actual model used this session** (per the harness attribution
reminder) — never a frozen/old example.

## 11. Hardware-test evidence
Build success is NOT sign-off for LVGL/task/lifecycle changes. Real-hardware serial/screen output
is ground truth; review task ownership, timers, and use-after-free before shipping such a binary.

## 12. Releases, notes, wiki & SD assets
A release attaches ALL binaries for ALL release boards. Refresh `ouilist.bin` (+ `mf_keys.dic`)
each cycle to `docs/support_files/` AND the separate `JimGat/CYM-SD-Assets` repo. The wiki is a
separate repo checkout. Details: `cym-release-workflow.md`.

## 13. Model routing / delegation  *(USER-CONFIRMED: model-agnostic cost tier)*
Cheapest available model for bulk grep/locate/search; current session model for reasoning and
implementation. Do NOT hard-code model names (the old "Haiku→Sonnet" split is retired). Spawn
subagents only when the user asks or a large search genuinely benefits. One task per invocation;
stop after ~3 build-fix cycles.

## 14. Memory, backlog & handoffs
Layered: tracked rules (this file + `.claude/rules/*.md`) → project auto-memory (`MEMORY.md` index)
→ session notes. **`BACKLOG.md` (repo root) is the canonical backlog** (there is no HERMES.md).
Keep memory small; update rather than duplicate; trim stale. Details: `cym-memory-discipline.md`.

---

### Reconciliation note (2026-09-24)
Created during a read-only workflow reconciliation. Resolved: version = same across boards per
cycle (not per-board); model policy = model-agnostic cost tier; Hosyond S3 = experimental/bring-up
now with release-board as a port-gated goal. Superseded "each board its own version" wording was
corrected in `cym-release-workflow.md`, `Makefile`, `~/.claude/commands/dev.md`, and the
`commit_format_rule` memory.

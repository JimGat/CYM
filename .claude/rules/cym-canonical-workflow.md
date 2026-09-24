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
Bump the PATCH digit (`Z`) in the SoC's `CMakeLists.txt` before any build that changes a binary,
sequentially (…v2.9.9 → v2.9.10 → v2.9.11…), never skipping or jumping to 99. Version bump is
manual (not automated by build.sh). Semantics:
- **Z (patch)** — default for all dev work; increment per changed build.
- **Y (minor)** — feature release; reset Z→0 (e.g. v2.9.99 → v2.10.0). Only on explicit user request.
- **X (major)** — major/breaking milestone; reset Y.Z→0.0. Only on explicit user request.

## 2. One version per cycle across boards  *(USER-CONFIRMED)*
All **release** boards built in a development cycle share the **same** version. Do NOT bump the
version separately per board. This supersedes any older "each board gets its own version bump /
no two binaries may share a version" wording (previously in cym-release-workflow.md, dev.md,
Makefile, commit_format_rule.md — all corrected).

**Source vs packaged version.** The authoritative version is the SOURCE `set(PROJECT_VER ...)` line
in the board's `CMakeLists.txt`: `ESP32C5/CMakeLists.txt` drives **both** NM-CYD-C5 and WS-C5-28;
`ESP32/CMakeLists.txt` drives CYD-2432S028. "Same version across boards" therefore means those two
files carry the same version for the cycle. That source version is compiled into each binary
(verify with `strings <bin> | grep vX.Y.Z`) and must be mirrored into each board's manifest JSON
(`"version"` + `"build"`). Hosyond (`ESP32S3/CMakeLists.txt`) carries an **independent** version and
is NOT synced.

**Source PROJECT_VER is the authoritative *intended* build version — it does not prove packaged
artifacts were rebuilt.** Because `ESP32C5/CMakeLists.txt` is shared by **both** NM-CYD-C5 and
WS-C5-28, bumping that one file sets the intended version for both boards, but only actually
**building each board** produces updated packaged artifacts (its `binaries-*/` app + `-full` images
and its manifest). So the source version alone cannot confirm either C5 board's artifacts are
current. **When reporting artifact status, verify each board's PACKAGED version from that board's
own manifest JSON and its application binary (`strings … | grep vX.Y.Z`) — not from the shared
CMakeLists.**

## 3. Skipped boards & drift
A release board deliberately skipped in a cycle stays at its prior version: its **existing binary
and manifest retain their previous version** (they are not rebuilt, so nothing changes for that
board). On drift, bring all release boards to `max_current + 1` in the next cycle. Do not hardcode
current versions in docs; read them from source (`CMakeLists.txt`, the intended build version) and,
for *packaged* status, from each board's own manifest + application binary (see §2).

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

**Build gate (USER-CONFIRMED):** every affected release board must build **green before any push**
in the cycle. Per-board commits are allowed, but do NOT push until all affected release boards are
confirmed building. (No push may leave `Jimgat_Dev` at a version that fails on some release board.)

## 6. Artifacts & packaging
Per-board binary set in `ESP32C5/binaries-esp32c5/`, `ESP32C5/binaries-ws-c5-28/`,
`ESP32/binaries-cyd-2432s028/`; per-board manifest JSON. Copy-to-export + `-full.bin` merge is
**automated** by the CMake POST_BUILD hook; version/manifest edits are manual. Details:
`cym-release-workflow.md`.

## 7. Commits
Subject = `vX.Y.Z: type(scope): description` (**version first**). Docs-only commits may omit the
version prefix (`type(scope): ...`). Stage board-specific files explicitly (never `git add -A`),
one logical change per commit.

**Push timing.** Push promptly after committing, but only after every affected release board has
passed the cycle's build gate (§5). Per-board commits may remain local until that gate passes.
Documentation-only changes that do not affect builds require documentation verification, not
firmware builds. (Completed, verified work must still be pushed — this does not weaken the build
gate; it sequences the push after it.)
Details: `commit_format_rule` memory + `cym-release-workflow.md`.

## 8. Branch & release authorization  *(partially enforced)*
Work on `Jimgat_Dev`. Merge to `main`, tag, or `gh release` ONLY on explicit user request.
Enforcement (truthful):
- **Hard-denied** (project `.claude/settings.local.json` deny): force-push (`git push --force/-f`),
  `idf.py flash`, `esptool write-flash`.
- **Soft-denied** (`~/.claude/settings.json autoMode.soft_deny` — a confirmation prompt, NOT a hard
  block): `git push … main …` and `gh release create …`.

### Enforcement reality (do not assume automation)
- **Instruction-only** (no automation, rely on this doc): version bump (§1), one-version-per-cycle
  (§2), the build gate (§5), commit format (§7), release-asset completeness (§12). CI does **not**
  build multi-board (`esp32c5-build-master.yml` is ESP32C5-only, on `main`/`master`), and nothing
  auto-bumps the version.
- **Automated**: CMake POST_BUILD packaging (copy to board `binaries-*/`, merge `-full.bin`);
  remember-plugin memory capture; the deny/soft-deny in §8 above; GitHub Pages flasher deploy on
  push to `main`.

## 9. Authorship & contributor credit
Default author `JimGat`. @birolt29's patches are authored **as him** (handle +
`birolt29@users.noreply.github.com`, NEVER his real name/email) and he is credited **co-developer**.
Other external contributors' own work is authored via their GitHub noreply address and credited in
README. Committer stays Jim. Details: `cym-contributor-attribution.md`.

## 10. AI attribution
`Co-Authored-By:` must name the **actual model used this session**. This is driven by the
per-session harness attribution reminder (NOT enforced by any repo hook), and the model string
changes session to session — copy the current one, never a frozen/old example.

## 11. Hardware-test evidence
Build success is NOT sign-off for LVGL/task/lifecycle changes. Real-hardware serial/screen output
is ground truth; review task ownership, timers, and use-after-free before shipping such a binary.

## 12. Releases, notes, wiki & SD assets
A release attaches ALL binaries for ALL release boards. The wiki is a separate repo checkout.
**SD-asset refresh (USER-CONFIRMED, staleness-gated):** at each release-to-main, check asset age;
if `ouilist.bin` (or `mf_keys.dic`) is older than **30 days**, refresh it and push to BOTH
`docs/support_files/` (this repo) AND the separate `JimGat/CYM-SD-Assets` repo; if fresher than 30
days, skip. Details: `cym-release-workflow.md`.

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

Second pass (JARVIS review of commit 5356935): added the portable entry point (`AGENTS.md`),
source-vs-packaged version handling (§2), the build gate — all affected release boards green before
any push (§5), truthful enforcement + AI-attribution wording (§8/§10), Y/X release semantics (§1),
and the staleness-gated SD-asset rule (§12). Lifecycle-duplicating memory files were converted to
pointers to this file.

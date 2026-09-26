# CYM-NM28C5 — shared-codebase multi-board build rule

## Background

Rebuilding CYD-2432S028 for the v2.13.89 sync (2026-09-13) surfaced a real, pre-existing
compile break: `radio_reset_to_idle()`'s 802.15.4 cleanup block called
`esp_ieee802154_sleep()`/`esp_ieee802154_disable()` completely unguarded. That's fine on
ESP32-C5 (which has 802.15.4 hardware) but a hard compile failure on the classic ESP32
(Xtensa, no 802.15.4 radio at all). It shipped unnoticed for six versions (v2.13.83–88)
because CYD-2432S028 hadn't been rebuilt since v2.13.80 — nobody ran its build until this
session, well after the breaking change landed on the shared source.

`ESP32/main/CMakeLists.txt` compiles `ESP32C5/main/main.c` and the `ot_survey`/`obs_store`/
etc. components **directly by relative path** — this is not a fork or a per-board copy, it
is one source tree feeding multiple `idf.py` targets. A change to that shared source is a
change to every board that compiles it, whether or not the change was written with that
board in mind, and whether or not anyone runs that board's build in the same session.

## Rule

**Any board that compiles shared source (`ESP32C5/main/*.c` and any component under
`EXTRA_COMPONENT_DIRS`/`PRIV_REQUIRES` referenced by more than one board's `CMakeLists.txt`)
must be rebuilt in the same session as any change that touches that shared source — not
just the board the change was written/tested for. All such boards must build clean before
the change is considered done.**

This is stronger than the existing multi-board **version-sync** rule in
`cym-release-workflow.md` (which allows a board to be "deliberately skipped" and stay at its
current version). That skip exception is for genuinely board-specific *feature* work — e.g.
a WS-C5-28-only screen, or a CYD2USB-only pin fix — where the other boards' compiled output
is provably unaffected because the change lives entirely inside a `CONFIG_BOARD_*`-gated
block or a board-specific file.

It does **not** apply when the change touches code a board's `CMakeLists.txt` actually
compiles. In that case "skip the build" is not a scheduling choice, it's an unverified
binary — the board may not even compile, and nobody will know until someone finally rebuilds
it, potentially versions later (as happened here).

### How to tell which one applies

Before skipping a board's build for a given change, check whether that board's
`CMakeLists.txt` (`ESP32C5/main/CMakeLists.txt`, `ESP32/main/CMakeLists.txt`, and any future
board's) lists the changed file in `SRCS` or references the changed component in
`REQUIRES`/`PRIV_REQUIRES`/`EXTRA_COMPONENT_DIRS`. If it does, that board compiles the
change and must be built. If the change is confined to a file or component the board's
`CMakeLists.txt` never references, or lives inside a `#if CONFIG_BOARD_<other>` block, the
board is untouched and the normal version-sync skip exception applies.

`ESP32C5/main/main.c` is compiled by **both** ESP32-C5 boards (NM-CYD-C5, WS-C5-28),
CYD-2432S028 (ESP32), and Hosyond ES3C35P 3.5 (ESP32-S3). A change there normally requires all
four release builds. `ESP32S3/main/CMakeLists.txt` compiles the canonical `ESP32C5/main/` sources
directly plus a narrow ES3C35P display/touch adapter; it is a shared-source consumer, not a stub or
compile canary. Hosyond 2.8-inch and 4.0-inch profiles remain experimental and outside this gate.

### Workflow

1. Identify every board whose `CMakeLists.txt` compiles the file(s) you changed.
2. Build all of them in the same session, in any order.
3. If a board that previously built clean now fails, that is not "pre-existing, not my
   problem" — the file is shared, so the failure is part of the same change. Fix it (adding
   the missing `#if CONFIG_IEEE802154_ENABLED`-style guard, or whatever the board actually
   needs) before considering the change complete. Do not comment out the board's build or
   quietly leave it broken for a future session.
4. Version-bump and commit all affected boards together per the existing multi-board
   workflow in `cym-release-workflow.md` — don't let one board's binary lag the others when
   they share the code that changed.
5. Only after all shared-codebase boards build green is the change done.

### What this does not change

- A board-specific feature that lives behind a `CONFIG_BOARD_*` guard, or in a file only one
  board's `CMakeLists.txt` references, still follows the existing "deliberately skipped"
  version-sync exception — no need to build every board for a WS-C5-28-only screen.
- This rule is about **build correctness**, not feature parity. CYD-2432S028 is expected to
  build 802.15.4-related shared code out entirely (no 802.15.4 hardware) — the rule is that
  it must still *build*, cleanly, not that it must have the same features.

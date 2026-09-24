# CYM-NM28C5 release/test workflow guardrails

When Jim asks for a change that he will test from GitHub, do the complete test-build handoff, not just source edits.

1. Work on the dev host repo: `/home/dev/projects/CYM-NM28C5`.
2. Stay on branch `Jimgat_Dev` unless Jim explicitly asks for `main`/release flow.
3. Before building a test binary, bump the PATCH version in `ESP32C5/CMakeLists.txt`:
   - `set(PROJECT_VER "vX.Y.Z")`
   - **All release boards built in a cycle share the SAME version** — do NOT bump the version
     separately per board. (This supersedes any older "each board gets its own version / no two
     binaries may share a version number" wording.) The version is a release marker meaning all
     release boards are at the same feature level.
   - Do not bump MAJOR or MINOR without explicit approval.
4. Build for the target board using the command for that board (see table below).
5. The CMake post-build hook copies firmware into the board-specific output directory and generates the merged full image. Verify all four tracked binaries changed.
6. Before commit, verify the binary contains the expected version string.
7. Update the board-specific manifest JSON to match the new version.
8. Stage board-specific files only (never `git add -A`), commit, and push to `origin Jimgat_Dev`.
9. Never run `idf.py flash`, `esptool write-flash`, or `git push --force` unless Jim explicitly overrides.

---

## Release boards vs experimental boards

**Release boards (3):** NM-CYD-C5, WS-C5-28 (both `ESP32C5/`), and CYD-2432S028 (`ESP32/`).
These are version-synced each cycle, must build clean for shared-source changes, and ship in
release assets + manifests + web flasher.

**Experimental / bring-up:** Hosyond S3 (`ESP32S3/`, targets `hosyond-s3-28/35/40`). Currently a
bring-up stub (its own ~372-line `main.c`, not the CYM app), pinned behind the release boards. It
is NOT version-synced and NOT shipped as a release asset. Promoting it to a release board is a
backlog goal gated on actually porting CYM to ESP32-S3 (see BACKLOG.md). `make all-boards` builds
`hosyond-s3-35` only as a compile canary.

## Multi-Board Build Reference (ESP32C5/)

All builds run from `ESP32C5/`. Load ESP-IDF first: `. /home/dev/esp/esp-idf/export.sh`

### NM-CYD-C5 (original CYM board)

```bash
idf.py -B build_nm-cyd-c5 \
  -DSDKCONFIG=build_nm-cyd-c5/sdkconfig \
  "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.nm-cyd-c5" \
  build
```

| Item | Value |
|------|-------|
| Output dir | `ESP32C5/binaries-esp32c5/` |
| App binary | `CYM-NM28C5.bin` |
| Full image | `CYM-NM28C5-full.bin` |
| Manifest | `ESP32C5/docs/manifest.json` |
| Web flasher board | `nm-cyd-c5` |
| Flash size | 16 MB |

Verify: `strings binaries-esp32c5/CYM-NM28C5.bin | grep vX.Y.Z`

Stage per commit:
```
ESP32C5/CMakeLists.txt
ESP32C5/docs/manifest.json
ESP32C5/docs/memory-budget.md
ESP32C5/binaries-esp32c5/CYM-NM28C5.bin
ESP32C5/binaries-esp32c5/CYM-NM28C5-full.bin
ESP32C5/binaries-esp32c5/bootloader.bin
ESP32C5/binaries-esp32c5/partition-table.bin
```
(plus any source files changed for that board)

---

### CYD-2432S028 (Classic CYD ESP32-2432S028)

```bash
cd ESP32
idf.py -B build_cyd2usb \
  -DSDKCONFIG=build_cyd2usb/sdkconfig \
  "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.cyd2usb" \
  build
```

Or from repo root: `make cyd-2432s028`

| Item | Value |
|------|-------|
| SoC dir | `ESP32/` (not ESP32C5/) |
| Output dir | `ESP32/binaries-cyd-2432s028/` |
| App binary | `CYM-CYD-2432S028.bin` |
| Full image | `CYM-CYD-2432S028-full.bin` |
| Manifest | `ESP32/docs/manifest.cyd-2432s028.json` |
| Web flasher board | `cyd-2432s028` |
| Flash size | 4 MB |
| Bootloader offset | 0x1000 (ESP32, NOT 0x2000) |

Verify: `strings ESP32/binaries-cyd-2432s028/CYM-CYD-2432S028.bin | grep vX.Y.Z`

Stage per commit:
```
ESP32/CMakeLists.txt
ESP32/docs/manifest.cyd-2432s028.json
ESP32C5/docs/memory-budget.md
ESP32/binaries-cyd-2432s028/CYM-CYD-2432S028.bin
ESP32/binaries-cyd-2432s028/CYM-CYD-2432S028-full.bin
ESP32/binaries-cyd-2432s028/bootloader.bin
ESP32/binaries-cyd-2432s028/partition-table.bin
```
(plus any source files changed for that board)

---

### WS-C5-28 (Waveshare ESP32-C5-Touch-LCD-2.8)

```bash
idf.py -B build_ws-c5-28 \
  -DSDKCONFIG=build_ws-c5-28/sdkconfig \
  "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.ws-c5-28" \
  build
```

| Item | Value |
|------|-------|
| Output dir | `ESP32C5/binaries-ws-c5-28/` |
| App binary | `CYM-WS-C5-28.bin` |
| Full image | `CYM-WS-C5-28-full.bin` |
| Manifest | `ESP32C5/docs/manifest.ws-c5-28.json` |
| Web flasher board | `ws-c5-28` |
| Flash size | 32 MB |

Verify: `strings binaries-ws-c5-28/CYM-WS-C5-28.bin | grep vX.Y.Z`

Stage per commit:
```
ESP32C5/CMakeLists.txt
ESP32C5/docs/manifest.ws-c5-28.json
ESP32C5/docs/memory-budget.md
ESP32C5/binaries-ws-c5-28/CYM-WS-C5-28.bin
ESP32C5/binaries-ws-c5-28/CYM-WS-C5-28-full.bin
ESP32C5/binaries-ws-c5-28/bootloader.bin
ESP32C5/binaries-ws-c5-28/partition-table.bin
```
(plus any source files changed for that board)

---

## Version numbering across boards

**All boards are kept in version sync** — every development cycle uses the **same** version number
for all boards that are built in that cycle.  This makes the version a meaningful release marker:
"v2.13.73" means all three boards are at the same feature level.

The exception is a board that is **deliberately skipped** in a cycle (e.g., a C5-only feature
that doesn't apply to CYD2USB).  When a board is skipped, it stays at its current version until
the next cycle that includes it.

### Re-sync rule (resolving version drift)
If boards have drifted (one board is ahead), bring all boards up to `max_current + 1` in the
next build cycle rather than continuing to diverge. For the current version of each board, read
the `set(PROJECT_VER ...)` line in that board's `CMakeLists.txt` (`ESP32C5/CMakeLists.txt` for
NM-CYD-C5 + WS-C5-28; `ESP32/CMakeLists.txt` for CYD-2432S028) — do not rely on a hardcoded number
here, which goes stale. As of this writing the three release boards are in sync.

### Workflow when building all boards in one session

1. Set version → v2.13.X in **both** `ESP32C5/CMakeLists.txt` and `ESP32/CMakeLists.txt`
2. Build NM-CYD-C5 → commit NM-CYD-C5 files at v2.13.X
3. Build WS-C5-28 → commit WS-C5-28 files at v2.13.X (same CMakeLists)
4. Build CYD-2432S028 (in `ESP32/`) → commit CYD-2432S028 files at v2.13.X

For CI verification across all boards: `make all-boards` (builds nm-cyd-c5, ws-c5-28, cyd-2432s028 in sequence).

---

## Release to main — MANDATORY binary attachment

When merging to main and creating a GitHub release, attach ALL binaries from ALL active boards:

```bash
gh release create vX.Y.Z \
  --target main \
  --title "..." \
  --notes "..." \
  ESP32C5/binaries-esp32c5/CYM-NM28C5.bin \
  ESP32C5/binaries-esp32c5/CYM-NM28C5-full.bin \
  ESP32C5/binaries-esp32c5/bootloader.bin \
  ESP32C5/binaries-esp32c5/partition-table.bin \
  ESP32C5/binaries-ws-c5-28/CYM-WS-C5-28.bin \
  ESP32C5/binaries-ws-c5-28/CYM-WS-C5-28-full.bin \
  ESP32C5/binaries-ws-c5-28/bootloader.bin \
  ESP32C5/binaries-ws-c5-28/partition-table.bin \
  ESP32/binaries-cyd-2432s028/CYM-CYD-2432S028.bin \
  ESP32/binaries-cyd-2432s028/CYM-CYD-2432S028-full.bin \
  ESP32/binaries-cyd-2432s028/bootloader.bin \
  ESP32/binaries-cyd-2432s028/partition-table.bin
```

Note: bootloader.bin and partition-table.bin differ between boards (flash size and offsets).
Use `--name board-filename` flags if GitHub CLI requires disambiguation.

`*-full.bin` is a merged flat image (bootloader + partition table + firmware) generated
by the CMake post-build hook. Flash at address `0x0000` with any full-binary flasher.
Never create a release without all binaries from all boards attached.

---

## SD card assets — refresh on every release

`ouilist.bin` (OUI vendor table, loaded from `/sdcard/lab/ouilist.bin` at runtime — it is
**not** baked into the firmware binary) goes stale as new MAC vendor blocks are registered.
Refresh it as part of every release cycle, not just when someone notices it's old (it went
~5 months stale between the 2026-04-29 and 2026-09-22 refreshes before anyone caught it):

```bash
curl -L https://standards-oui.ieee.org/oui/oui.csv -o /tmp/oui-fresh.csv
python3 tools/oui_convert.py /tmp/oui-fresh.csv /tmp/ouilist-fresh.bin
# sanity check before committing anywhere:
python3 -c "import struct; f=open('/tmp/ouilist-fresh.bin','rb'); print(f.read(4), struct.unpack('<I', f.read(4))[0])"
```

This must be pushed to **two** places, both required:

1. **`docs/support_files/`** in this repo (`oui.csv` + `ouilist.bin`) — the staging/source
   copy tracked alongside the firmware that generated it.
2. **[JimGat/CYM-SD-Assets](https://github.com/JimGat/CYM-SD-Assets)** — the actual
   distribution repo end users download onto their SD card
   (`oui.csv` at root + `sdcard/lab/ouilist.bin`). Update `ASSET_MANIFEST.md` there too
   (generation date, entry count, SHA256 of both files) — that repo has its own copy of
   `tools/oui_convert.py` and documents this exact refresh procedure in its own README.

CYM-SD-Assets is a separate repo (`git@github.com:JimGat/CYM-SD-Assets.git`) — clone it
locally if not already present, don't try to push SD-asset changes through this repo.

The RFID key dictionary (`mf_keys.dic`, sourced from RfidResearchGroup's Proxmark3
dictionaries) lives in CYM-SD-Assets only, not here — refresh it the same release cycle if
it's gone stale (see that repo's README for the source URL and refresh command).

---

## Web flasher (ESP32C5/docs/index.html)

The flasher supports board selection at runtime:

| UI selector | SoC | Manifest | Binary directory |
|-------------|-----|----------|-----------------|
| NM-CYD-C5 | ESP32C5 | `ESP32C5/docs/manifest.json` | `ESP32C5/binaries-esp32c5/` |
| WS-C5-28 | ESP32C5 | `ESP32C5/docs/manifest.ws-c5-28.json` | `ESP32C5/binaries-ws-c5-28/` |
| CYD-2432S028 | ESP32 | `ESP32/docs/manifest.cyd-2432s028.json` | `ESP32/binaries-cyd-2432s028/` |

To add a new board to the web flasher, add an entry to the `BOARDS` object in `docs/index.html`
and create the corresponding `docs/manifest.<board>.json`.

---

## Runtime crash discipline

- Build success is not enough for LVGL/task/lifecycle changes.
- For sniffer/capture/UI teardown work, specifically review task ownership, timers, global pointers, cancellation, and use-after-free risks before publishing a binary.

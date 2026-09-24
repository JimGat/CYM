# CYM Backlog

Consolidated backlog for CYM-NM28C5. This is the single tracked list of planned features,
integrations, hardware directions, and known tech debt. Detailed design notes for larger
items live in commit history, the wiki, and the maintainer's working notes; this file is the
index and status tracker.

Status key: **IDEA** (captured, not scoped) · **PLANNED** (scoped, ready to start) ·
**IN PROGRESS** · **BLOCKED** · **TABLED** (deliberately deferred).

Last updated: 2026-09-23.

---

## Features (firmware)

- **BLE / WiFi Chat** — IDEA. Device-to-device off-grid messaging between CYM units (and
  potentially other ESP devices) over BLE and/or WiFi. Long-wanted. Open questions: transport
  (BLE GATT vs advertising vs ESP-NOW vs SoftAP), peer model (CYM↔CYM only vs open), and how it
  shares the single WiFi+BLE radio with other features. *(new 2026-09-23)*

- **ESP-NOW Listener / Debugger** — PLANNED. Passive ESP-NOW traffic detection + a
  device/session table and live packet log; channel-hop discovery vs fixed-channel capture;
  CSV/JSON export to `/sdcard/lab/espnow/`; known-key (LMK) decode for Jim's own devices.
  Staged: passive detect → known-key profiles → native RX/decode → advanced passive decrypt.
  Dedicated listener mode must suspend normal WiFi while channel-hopping (single shared radio).
  Full spec in CLAUDE.md "Next Feature Idea".

- **BLE Spoof Honeypot** — PLANNED. Connectable spoofed device that logs connection attempts
  (who is seeking the cloned device). Extends the existing BLE spoof/clone work.

- **CC1101 high-band support** — IN PROGRESS. `g_cc1101_highband` flag is in place; still needs
  NVS wiring + a Settings tile. Note: the NM-RF-HAT LC filter is only rated 315/433 MHz.

- **BT Lookout — OUI Groups screen** — PLANNED. OUI system is done; add an OUI Groups UI and
  more vendor groups.

- **BMorcelli Launcher support (NM-CYD-C5)** — DONE. CYM is compatible with
  [bmorcelli/Launcher](https://github.com/bmorcelli/Launcher) and available in its Beta Release
  channel (CYD → NM-CYD-C5); the app-only `CYM-NM28C5.bin` runs from `app1` (ota_0), no
  conversion needed. *(corrected 2026-09-23 — was wrongly tabled as incompatible)*

- **Launcher support — WS-C5-28 & CYD2USB** — PLANNED. Both are **binary-compatible** with
  bmorcelli/Launcher (app-only bins run from the Launcher's OTA slot, same model as NM-CYD-C5).
  Only remaining step is getting them **added to the Launcher Beta channel** so they're
  selectable there — no firmware work needed. *(new 2026-09-23)*

---

## Satellite / external-device integration

Detailed protocol/phasing plan exists (Biscuit GATT UUIDs, JANOS command set, coexistence
rules). Start ONE track at a time; do not run all simultaneously.

- **Biscuit wireless support (BLE satellite)** — PLANNED. NimBLE GATT central to a Biscuit
  Pro/Ultra: time-sync from CYM GPS, request 5GHz wardrive from Biscuit while CYM does 2.4GHz
  (zero band overlap), GPS-stamp + merge Biscuit AP records into the wardrive table (source-tag
  'B' vs 'C'). Needs on-hardware coexistence validation (BLE connection + WiFi promiscuous).

- **Biscuit multi-node C5 mesh** — IDEA. Use the Biscuit ESP-NOW mesh (Pro/Ultra hub + multiple
  ESP32-C5 DIY nodes) as a distributed multi-C5 radio array aggregated to CYM over one BLE pipe.
  Because Biscuit DIY nodes are ESP32-C5 (dual-band 2.4+5GHz), this also gives CYM distributed
  5GHz coverage — the complement to the S31 (2.4GHz-only) direction below. *(new 2026-09-23)*

- **MonsterC5 / JANOS via UART** — PLANNED. UART link (CYM GPIO8/9 JST while no RF-HAT is
  installed) to a Lab5 MonsterC5 running JANOS/projectZero: `ping`/`version`/`scan_networks`,
  independent wardrives merged post-session via JANOS admin-portal HTTP download (identical
  WiGLE CSV schema). Monster has its own radio → zero coexistence conflict. Later: relay
  jammer/Zigbee/RF commands.

- **MonsterM5 support** — IDEA. **Needs clarification: distinct device from MonsterC5?** Likely
  the M5Stack-format "M5 Monster" (not the ESP32-C5-WROOM MonsterC5). If so its MCU/firmware and
  command interface may differ from JANOS — confirm before reusing the MonsterC5 UART plan.
  *(new 2026-09-23)*

- **JANOS-RF relay** — IDEA. Relay MonsterRF's 72 RF protocol families (KeeLoq, Somfy, etc.)
  through CYM UI. RF command set not public yet — get from the C5Lab developer.

---

## Hardware / boards

- **CYM Adapter Carrier Board** — PLANNED (design). Carrier connecting a Lab5 MonsterC5/MonsterRF
  to CYM, with onboard battery + charging. CYM becomes the display/UI/WiFi front-end; Monster
  handles RF. Supersedes the earlier "custom CYM HAT" idea.

- **Terminal Screen** — IDEA. Raw terminal UI on CYM for direct Monster command/output — debug
  and pre-UI features.

- **Flipper expansion-board adapters** — IDEA. Adapters to use Flipper Zero expansion modules via
  CYM/Monster GPIO/UART passthrough.

- **ESP32-S31 evaluation** — IDEA. New dual-core RISC-V 320MHz SoC with WiFi6(2.4GHz-only) +
  BT5.4(Classic+LE) + 802.15.4 + Gigabit Ethernet MAC. NOT supported by our pinned IDF v6.0.2
  (preview/master-branch only) — evaluate in an isolated IDF install; do NOT move CYM's main IDF
  to master. Does NOT replace the C5 (2.4GHz-only WiFi; C5 remains the only dual-band 2.4+5GHz
  part), so a full-capability S31 CYM = S31 + C5. Dual-core could fix the single-core jammer
  timing limit. Board on order (2026-09-23).

- **ESP32-S3 board port (Hosyond)** — PLANNED. 2.8" ILI9341+FT6336G and 3.5" ST77922 QSPI boards;
  GPIO maps documented, `ESP32S3/` skeleton exists from the multi-board framework. Single-chip
  (WiFi+BLE), closest sibling to current boards — lowest-lift next target.

- **Multi-board framework — remaining phases** — IN PROGRESS. Phase 1 done (Makefile,
  per-SoC `build_<board>/` dirs, ESP32/ + ESP32S3/ skeletons). Later phases per the framework
  plan.

- **CYM case print** — TODO. Choose/print a case; verify stack height, display/touch cutout,
  USB-C + SD access, antenna clearance, and whether NM-RF-HAT DIP switches need external access.
  Candidate case links in README.

---

## Tech debt / cleanup

- **Battery ADC** — BLOCKED. `ADC_CHANNEL_5` maps to GPIO6 (also SPI SCK); configuring it breaks
  display/touch. Permanently disabled (`if (false && ...)`); battery UI shows nothing. Needs a
  different sense path or hardware change.

- **SD mount at 20 MHz** — OPEN INVESTIGATION. Mount sometimes fails at 20 MHz on some setups.
  Distinct from the (resolved) flash-confusion stuck-card issue and from the CYD mode-0 ACMD41
  issue. Decision on record (2026-09-23): "let it ride" — no SD-driver change; if it recurs,
  capture the failing SD command from the serial log to pick the fix (freq-fallback vs mode-3).

- **Debug scaffolding removal** — CLEANUP. `DBG-XX` macros and `[MAIN LOOP] Alive` log in main.c
  are safe to remove once no longer needed for diagnostics.

- **ft6336.c/h removal** — CLEANUP. Old capacitive-touch driver on disk but not compiled; remove
  when convenient.

---

## Tabled / not pursued

- **Monster Whisperer integration** — TABLED (2026-04-19). 6-phase ESP32-S3 BLE gateway plan
  superseded by the carrier-board + JANOS-UART direction.

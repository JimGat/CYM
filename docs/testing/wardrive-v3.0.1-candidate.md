# v3.0.1 Wardrive development candidate

Status: software regression reproduced and host-tested; physical capture acceptance pending. This is a Development candidate, not a Stable release.

## Reported targets

- Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35). Owner serial captures: v2.15.99 and v3.0.0, boot and SD mount completed.
- Waveshare ESP32-C5-Touch-LCD-2.8 (WS-C5-28). Owner reports immediate STOPPED.
- NM-CYD-C5. Owner additionally reports the same Wardrive symptom; no NM Wardrive serial capture was supplied. The separately reported NM boot issue remains separate.

## Reproduction and correction

The harness extracts the real production BLE cleanup/session/callback and task finish/reap helpers, plus the actual WiFi admission fragment. SDK, clock and mutex boundaries are deterministic mocks, not RF evidence. Before the patch, a WiFi-only session with no BLE table, initialized port or callbacks nevertheless requested the LVGL mutex for 100 ms. A 350 ms UI hold made session admission return false, leading to zero-network exit and the incorrect BLE-only log. Immediate-lock controls passed. This proves the software failure mechanism, not which predicate fired on a particular physical board.

Resource-free cleanup now avoids that UI dependency only after closing callback admission, joining any owned NimBLE port and draining in-flight callbacks. Retained tables still require the same bounded mutex and are never freed underneath readers. Startup retries transient ownership contention with yielding, cancellable waits (ten attempts and a one-second retry window, retaining each attempt's existing bounded host/callback waits); terminal deinit failures remain blocked. No radio-mode-only cleanup bypass or indefinite wait was added.

WiFi filter/callback/enable API errors now reject startup with exact predicate/return code; failed admission no longer prints BLE-only. Both dashboard update paths show START, active channel/SCAN, STOPPING, CLEANUP, FAILED or STOPPED according to actual lifecycle readiness. BLE-only SCAN is published only after successful scan startup. CSV/schema, SD frequency, GPS, console, regulatory policy, bootloaders and partitions are unchanged.

## Contributor evidence and patch review

@birolt29 independently diagnosed the same lock-dependent startup failure on hardware. His v3.0.0 report includes eight NM-CYD-C5 runs with WiFi/BLE transitions, 13-18 WiFi APs per successful run, BLE CSV output, and additional confirmation on Classic CYD-2432S028, Hosyond ES3C35P 3.5 and WS-C5-28 WiFi-only. These are contributor bench reports for his supplied patch, not physical qualification of this candidate. His Back-exit versus Home-exit reproduction is part of the acceptance checklist.

The supplied main.c-only patch was preserved and applied successfully to an isolated authentic v3.0.0 source fixture on ESP32-Dev. Its WiFi-only path continues after UI-lock contention, corroborating the diagnosis. It also continues when cleanup is refused for an unjoined NimBLE host, terminal SDK deinit failure or callbacks still in flight; actual-production-helper fault injection reproduced those unsafe admission decisions. Thus its blanket continue-on-cleanup-failure behavior was not imported. This candidate retains bounded orderly ownership checks rather than treating every false cleanup result as UI contention. Table reuse is not itself a leak: the rejected aspect is reuse/radio admission without proven callback/host quiescence.

Separate contributor-reported finding: WS-C5-28 BLE-only scan can fail with BLE_ERR_MEM_CAPACITY (ogf=0x08, ocf=0x0042, hci_err=0x207), with about 450 bytes of DMA-capable memory after NimBLE init. The reported pre-init headroom is about 30.5 KB and NimBLE consumption about 30 KB; the display/touch/audio allocation explanation remains a hypothesis. This candidate does not fix or independently reproduce that physical DMA-budget issue. Do not confuse WiFi-only startup recovery with WS-C5-28 BLE acceptance.

## Physical operator procedure

1. Use the board-specific v3.0.1 application image listed in the completed candidate report. Verify its SHA-256 and installed matching production partition layout. Connect only the Primary USB-C programming/debugging console at 115200 baud. Do not reconfigure the GPS UART or send debug to it.
2. Prefer application-only write at 0x10000 with erase-all disabled. Do not write the bootloader, partition table, NVS or PHY regions. The immutable full-image URL is supplied for completeness at 0x0000; it is not the settings-preserving choice. A merged full image can erase NVS/PHY sectors even where bytes are 0xff and erase-all is disabled. No SD format, NVS erase or partition migration is requested.
3. Capture boot through the installed v3.0.1 banner, SD mount, selected radio mode, GPS choice, START and [WD_START] diagnostics. Start WiFi-only Wardrive using the same GPS choice that previously failed.
4. Verify channels advance, packet/network counters increase, and the new WD_Wifi_*.csv contains valid captured network rows (not just a header). Record filenames and several sanitized network rows. START or a visible dashboard alone is not success.
5. Stop normally, wait for STOPPED and completion; CLEANUP means ownership is retained, not completed. Test Back exits as well as the top-bar Home reset path. Restart at least three times without rebooting, verifying fresh CSV output and advancing counters each time. Exercise both Classic and Modern access to the shared Wardrive screen.
6. Test BLE-only startup/counters/file rows, normal stop and repeated restart; return to WiFi-only and repeat. SCAN alone does not establish BLE capture. Cancel once during START and verify no unsafe restart or stale callback/table behavior. If a failure remains, retain the exact predicate, return code, mode, table/port/callback counts and subsequent cleanup output.
7. Repeat on WS-C5-35, WS-C5-28 and NM-CYD-C5. NM boot failure, if present, prevents its Wardrive test and must be reported with its own boot capture; do not attribute it to this fix.

No device was remotely flashed. Stable/main/tag/release and the live Stable flasher must remain unchanged.

# v3.0.15 Development: scoped ownership, console and DHCP

## Scope and evidence limits
Development candidate only; no Stable promotion or flashing. All eight profiles retain their display transport/buffers, stack capacities, SPI clocks, GPS routing, NVS and both UI layouts. Classic/HackerBox retain intentional debug/mDNS exceptions. Build/host evidence is not physical acceptance.

- Native USB debug worker reserves its existing 4096-byte internal stack before later application allocations, and reports allocation, streams, parser, registration and task-start failure stages separately. This reservation is reliability capacity, not a RAM saving.
- mDNS gets a build-local, hash-pinned dependency overlay with stop admission, queue draining and dependency-safe cleanup. Internal-stack allocation limits remain; no external mDNS task stack experiment is included. Intentional Classic/HackerBox status is Disabled, not Failed.
- OT scheduler retains stack/TCB ownership, parks cooperatively and requires suspension plus off-core proof before retirement. Timeout preserves ownership/admission. PSRAM profiles do not silently retry with a dynamic internal stack; no-PSRAM profiles retain their existing internal task path.
- Seven legacy tool queues publish producer disable and drain readers before reuse. Eligible payloads use PSRAM, with bounded fallback on no-PSRAM profiles. Stop retains inspection data; Home disables eligible producers. Portal uploads allocate the 1 MiB PSRAM buffer only on upload and free it on Stop. No display DMA buffer reduction.

## WS-C5-28 DHCP investigation
Source inspection identified lifecycle and visibility defects, not a reproduced field root cause:

1. Ensure existing/default STA and AP netifs are found/created before Wi-Fi start. Check saved-config/start/connect errors rather than reporting a connection unconditionally.
2. Clear cached IPv4 on disconnect, STA stop and lost-IP. Accept GOT_IP only for the current STA interface; association is not an address lease.
3. NTP initialization no longer publishes success before callback/netif dependencies succeed. UI distinguishes association, waiting for DHCP and current address, with typed netif/client-state and allocation diagnostics.

Memory pressure remains a hypothesis. No claim is made that the owner's DHCP failure is fixed without correct-board hardware evidence. BLE reception and mDNS allocation success are also not established by these changes.

## Field acceptance: primary USB-C, correct board, no erase-all
Use the Development board selector for Waveshare ESP32-C5-Touch-LCD-2.8 (WS-C5-28), not another C5 application. Preserve settings; no remote flashing was performed. App-only updates require the matching existing partition layout and application offset 0x10000.

1. Open the primary USB-C serial terminal with carriage-return input. After boot, send `debug status`, then `debug on`, then `debug query`. Expected: real command replies; the UI console status becomes Ready after worker input handling starts. Logs alone are not proof of command input. If initialization fails, preserve its precise failure stage and error.
2. In Clock/NTP, connect using saved Wi-Fi. Expected progression: association -> waiting for DHCP -> nonzero IPv4 -> NTP success. Capture DEBUG_CONN, DEBUG_WIFI_NETIF, DEBUG_NTP and DEBUG_HEAP records from before connection through failure/success. Do not disclose SSIDs, addresses or credentials publicly without redaction.
3. Disconnect/reconnect or enter/leave a Wi-Fi tool, then reopen Clock/NTP. Expected: no stale IPv4 after disconnect/lost-IP, no netif duplication, and either a fresh address or truthful waiting/failure diagnostics. Repeat in Classic and Modern layouts.
4. Exercise repeated OT entry/stop/home/re-entry. Expected: no stranded caller-owned stack/TCB; a stop timeout retains ownership and rejects conflicting radio work instead of force-deleting a running task.
5. Check legacy tool Stop-to-inspect, Home-to-release/reopen; portal repeated uploads/Stop; QR/Observer/SD/rotation/GPS/background timekeeping. Compare warmed-cycle internal-largest-block and PSRAM readings rather than asserting fresh-boot savings from cumulative queue capacity.

## Automated gates
Independent parent regression: 660 tests, no failures/errors, one private-capture skip; targeted ASan/UBSan production-source harnesses for console, mDNS queue/stop, netif/IP, OT lifetime, legacy log lifetime, owner behavior, NTP/Clock and memory boundaries. Parent review added a failing-then-passing OT allocation/admission case. All eight profiles were rebuilt after that final source fix, sequentially with two compiler jobs, resource stop gates and per-board telemetry. Package gate verifies application descriptors, board flags, offsets, partitions, generated/package equality and 32 artifact entries. Deployment must additionally verify exact-head Pages, live selectors and Stable asset preservation.

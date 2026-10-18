# Clock mDNS headroom candidate — v3.0.20 Development

Status: software/build/package verified; physical repair acceptance remains OPEN.
No Stable release or device flash is implied.

## Diagnosis and scope

The v3.0.19 capture from Waveshare ESP32-C5-Touch-LCD-2.8 (WS-C5-28)
shows two genuine failures allocating the unchanged 4096-byte internal mDNS
stack: internal free 3158/3402 bytes, largest block 3072 bytes both times.
Millions of free PSRAM bytes cannot satisfy that internal-only request.
NTP starts first; startup logs alone do not prove a UDP/123 reply.

The single firmware behavior change applies the existing `PSRAM_ATTR` to
`s_det_records`, the retained Chameleon MF1 Detect decoded-record table.
It is ordinary cached UI-task data: parsing is dispatched by `cham_poll`,
and export reads it in the LVGL task. No DMA, ISR or cache-disabled consumer
was identified. Capacity, zero initialization and static lifetime are unchanged;
there is no new allocation, fallback, free, disabled feature or broad refactor.

Actual final ELFs place the 5120-byte table in `.ext_ram.bss` on all six
PSRAM targets, reducing linked internal allocation by exactly 5120 bytes each.
Classic CYD and HackerBox retain their existing 640-byte internal table and
unchanged linked internal totals. This is target-linked evidence, NOT a measured
5120-byte increase in the live contiguous heap or proof that mDNS now starts.

The internal 4096-byte mDNS stack/RTOS controls, NTP-first order, existing NTP
stack policy, accepted USB console, normal FSD, both navigation layouts, display
buffers, GPS/RTC/Client arbitration, pins, SD speed, NVS and partitions are unchanged.
Classic/HackerBox still show mDNS Disabled by board capability.

## Software verification

- All eight final-source board builds and their packaged v3.0.20 versions verified.
- 678 regression tests: 677 passed, one skipped, zero failures/errors.
- Actual-declaration placement/consumer regression was RED before the change;
  final four cases pass, including both memory classes and sanitized parser/export/stop use.
- Production mDNS allocation/unwind/debug cases, Clock ownership, console and
  FSD lifecycle/real-LVGL tests pass; host models are not physical acceptance.
- All bootloader/partition images remain byte-identical to the prior cycle.

## Bench procedure and expected results

Use the board-matched Development image. For settings-preserving tests, use the
app-only image at `0x10000` only with the matching existing partition layout and
Erase All OFF. A full image at `0x0000` is not settings-preserving. Do not format SD
or erase NVS. Start with WS-C5-28, then Waveshare ESP32-C5-Touch-LCD-3.5 (WS-C5-35).

1. Connect commands/logging only to primary USB-C at 115200. Confirm board and
   v3.0.20 in the boot log, normal display/touch and SD mount at 20 MHz.
2. Enter `debug on`, then `debug status`. Expect ON applied immediately.
3. Open Clock -> AP NTP. Join the displayed AP from a separate client.
   Expect NTP startup before mDNS and `Registered cym-ntp.local`.
   Save the exact `stage=stack phase=before bytes=4096` free/largest values and
   successful after-result. Capacity must cover the request plus overhead and
   operating margin; a successful allocation with no margin is not qualification.
4. On Linux on the same Wi-Fi, run `timeout 20 avahi-browse -rt _ntp._udp` and
   `avahi-resolve -4 -n cym-ntp.local`. On Bonjour/macOS, use
   `dns-sd -B _ntp._udp local.` and `dns-sd -G v4 cym-ntp.local`, stopping each
   after 20 seconds. Expect the current Clock IP and port 123, not a stale cache.
5. Verify actual UDP/123 replies from that IP with an NTP query client without
   setting the PC clock. Record reply source, matching originate timestamp,
   LI/stratum and the Clock request count. LI=3/stratum=16 is a service response,
   not qualified time. GPS/RTC/Client source quality must be checked separately.
6. Repeat AP -> Home -> AP ten times, waiting for stop/reap; then
   AP -> Home -> Client -> Home -> AP. Recheck discovery/UDP on later cycles.
   Save each allocation boundary and settled stop values; check for crashes,
   stuck owners, heap drift, lost console or broken display/touch.
7. Repeat with `debug off`, verify immediate OFF and persistence after reboot.
   Run both Classic and Modern navigation paths; retain no-console behavior on
   Classic/HackerBox rather than expecting unsupported debug commands there.

## Related-feature regression checks

Most direct impact: Chameleon MF1 Detect multi-batch parsing, bounded records,
export to SD, exit/Home/reentry, and normal NVS/flash activity while using PSRAM.
Use only authorized lab records and keep decoded payloads private. Also verify
GPS/RTC/Client time selection, SD at its existing speed, display/rotation/touch,
FSD forward/Back/Home, USB debug responses, and normal radio transitions.
Do not disable intentional background services to manufacture memory headroom.

Return a private serial capture plus board/version, cycle counts, minimum actual
stack-boundary free/largest, discovery/UDP outcomes, time-source quality, and
regression observations separated by debug ON/OFF. Until then, mDNS headroom
repair, leak-free operation and physical cache safety remain unqualified.

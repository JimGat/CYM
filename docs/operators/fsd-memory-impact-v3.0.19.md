# FSD memory impact — source/ABI audit, not live headroom proof

Baseline caf07ea3ed2afc1bc64bf96c22215cc8b7a2bddc (v3.0.18). No mDNS headroom repair.

## New retained state
Actual WS-C5-28 target compiler (recorded compile flags/includes from production
compile_commands.json) reports cym_fsd_request_t=400 bytes, IDF cmd_item_t=32,
esp_console_cmd_t=28. Native host ABI request=408: not substituted for target size.
Target sizes were checked with the production WS-C5-28 compiler and flags.
Linked enabled-board symbols identify exactly 12 new static writable bytes:
s_fsd_pending=4, s_fsd_busy=4, fsd_registered=4. The 13 constant command definitions
occupy 364 flash-rodata bytes. No new FSD task, semaphore or RTOS queue exists.

Idle command registration is NOT free: 13 production IDF linked-list entries
request 416 bytes total plus 106 bytes of hint string payload, excluding allocator
alignment/metadata and transient asprintf scratch. IDF uses configured default
heap caps for entries and libc asprintf for hints. Small allocations may consume
internal SRAM under the existing PSRAM malloc threshold; treat this additional
522-byte payload as a new headroom cost, not a saving or live free-block delta.
No global console allocator policy was changed. FSD registration uses the existing
console and unwinds only its own partial registrations on failure; debug remains.
Real target boot allocation/capability tracing is still required.

## Bounded command storage
One request at a time, 400-byte PSRAM request on supported boards. Tree adds at
most 24,576 bytes PSRAM (24,976 payload total). No PSRAM-to-internal fallback in
FSD-owned request/tree/RGB/row buffers. An unstarted timed-out request retains one
owner reference until the UI loop drains; it is bounded, not prematurely freed.
A permanently stalled UI can retain this one request, blocks later requests, and
needs operator recovery. Running cancellation also preserves buffers until owner
completion. No detached timer or callback can acquire a pointer to reused state.
ASan/UBSan real-mailbox two-thread run exercised 10,000 requests (5,000 caller
cancellations, 5,000 completions), zero outstanding allocations after drain.
This is host concurrency evidence, not ESP scheduler/cache-disabled qualification.

Screenshot RGB888 output=3*W*H, root RGB565 snapshot approximately 2*W*H,
optional alpha-overlay snapshot approximately 3*W*H. Root+RGB peak approximately
5*W*H, overlay peak approximately 8*W*H, PLUS LVGL descriptors/draw scratch and
allocator metadata. At transfer time snapshots are freed; retained RGB plus a
4*W+1 byte base64 row and request remain. Existing LVGL allocation policy tries
PSRAM then MALLOC_CAP_8BIT fallback; its own scratch/metadata can still consume
internal heap. FSD does not claim zero command-time internal pressure.

| Profile geometry | Logical W x H | RGB bytes | Root+RGB approx | With overlay approx | Base64 row bytes |
|---|---|---:|---:|---:|---:|
| NM-CYD-C5 / WS-C5-28 | 240x320 | 230,400 | 384,000 | 614,400 | 961 |
| WS-C5-35 / Hosyond | 320x480 | 460,800 | 768,000 | 1,228,800 | 1,281 |
| Pancake-C5 | 480x320 | 460,800 | 768,000 | 1,228,800 | 1,921 |
| WS-S3-5B logical | 512x300 | 460,800 | 768,000 | 1,228,800 | 2,049 |

Logical dimensions are bounded to 800 per axis. Width/height and complete data
are validated on the PC; no short-image padding or invented frames. LVGL drawing
can create/cache its own working state; physical repeated-capture heap-minimum
and largest-block measurements remain required. Static/linker deltas below must
not be interpreted as this runtime behavior or as reclaimable contiguous SRAM.

## Existing memory controls preserved
Existing lvgl_memory.c remains PSRAM-first with its previous fallback, unchanged.
Display buffers and DMA placement, GPIOs, SD 20MHz, NVS/partitions, console USB-only
routing and 4096-byte internal debug worker are unchanged. OUI binary table
(32-byte entries) already allocates in PSRAM, persists as its own owned cache and
has an explicit unload; it is not a proven reclaim of internal contiguous SRAM.
The reported approximately 434KB BT Observer retention is not established as a
fresh-boot live internal owner by this run. No table was freed speculatively and
no background capability was disabled. No global placement switch was added.

The existing mDNS responder cleanup fix, diagnostic overlay, NTP-first ordering, 4096-byte internal stack and internal RTOS controls are preserved. The earlier data-only PSRAM experiment did not establish sufficient headroom.

Owner WS-C5-28 evidence: 8MB PSRAM, before mDNS after NTP free4314/largest3840;
just before 4096 internal stack request free3622/largest3456; NO_MEM257; after
unwind free4314/largest3840. This is supplied physical evidence, not recreated by
our host allocator. mDNS headroom remains OPEN. Additional FSD registration costs
can worsen that boundary. No stack shrink/externalization, speculative reservation,
unsafe live free, or invented successful resolution is offered.

## Final linker/config results
Final-source results: enabled boards all show +16 linked internal bytes (12 bytes
of named FSD writable state plus link/alignment effects), disabled boards +0.
Eight generated sdkconfig files are byte-identical to the v3.0.18 safety-cycle
records; config/sdkconfig.h hashes are distinct files and were not used as that
baseline comparator. Generated configuration and linked symbols were independently compared. Native/ABI probes are not device acceptance.

| Board | App-byte delta vs v3.0.18 | Linked internal-byte delta |
|---|---:|---:|
| nm-cyd-c5 | +11712 | +16 |
| ws-c5-28 | +12032 | +16 |
| cyd-2432s028 | +16 | +0 |
| hosyond-s3-35 | +9456 | +16 |
| ws-c5-35 | +11856 | +16 |
| pancake-c5 | +11264 | +16 |
| hackerbox-cyd | +16 | +0 |
| ws-s3-5b | +9232 | +16 |

Console-none app +16 bytes is not FSD code/data: its empty FSD object and absent
FSD linked symbols establish exclusion; navigation/version changes are shared.

## Related-function regression checklist


| Area | Production code / test evidence | Scope and remaining gap |
|---|---|---|
| Windows fixes | test_fsd_build_nav: AST-extracted real replace_section literal backslashes; GNU ar native extraction/transformed object equivalence | Native Linux ar passed. Native Windows binutils execution pending. |
| Back/history/Home | test_fsd_build_nav compiles real nav stack/back/show_menu/stop functions; absent/present explicit parent, shortcut, repeated Back, Home, both layout branches, stop-before-reset/deletion | Extracted production functions, synthetic surrounding SDK; not full physical UI. |
| UI request scheduling | source-order regression places FSD before existing transition gate; real LVGL rejects direct nav/rotate during exclusive screen | UI owner under existing mutex, no cross-thread lv_async_call; physical transition/stop qualification pending. |
| Console registration/parser | run_fsd_host real fsd_console.c: each 13 registration failure positions/unwind, repeat/unregister, integer overflow/suffix/range/label bounds, timeout/retry; existing targeted_console and console_stream | Synthetic IDF allocation/transport boundaries; accepted debug worker/stream regressions passed. |
| Bounded request lifetime | real fsd_lifecycle.h: queue publication failure, allocation failure, pending timeout, late event completion; actual LVGL screenshot caller cancellation while snapshot remains live; ASan/UBSan concurrent mailbox 10000 requests | Zero tracked outstanding mailbox allocations after drain; LVGL process-global objects intentionally excluded from leak detector, not represented as full-process no-leak proof. |
| Widgets/modal/disabled | real LVGL tap ID/text/coordinate, hidden/disabled, overlay capture, deletion on each of 4 events, disable-on-press abort, tree depth/output bound, move/size/text | 7 logical geometries x 2 synthetic container layouts per variant; not physical touch or complete application layout rendering. |
| Screenshot policy | real LVGL root and alpha overlay composite pixel, brightness overlay restore, dimensions/RGB OOM/cancel; real parser framing; synthetic PC bad/missing/reordered rows and crash text | No global log suppression/reset; physical panel scaling/color and actual continuous UART throughput pending. |
| PC safe automation | test_fsd_pc synthetic transport: reviewed routes validated before open, initial/destination truth, heap/screenshot requirements, raw/crash retention, skipped children, connection/report failures, cleanup | No device connected and no transmitting automation executed. |
| mDNS safety | targeted_mdns plus 40 production allocation/unwind/reinit/debug scenarios; overlay/SDK config hashes preserved | INTERNAL 4096/NTP-first/UAF diagnostics unchanged; physical WS-C5-28 failure remains OPEN. |
| Existing lifetimes/time/memory | targeted_owner, netif_lifecycle, legacy_log_lifetime, ot_lifetime, ntp_clock_owner, memory_boundary | Native production extraction/stub boundaries; no new physical WiFi/BLE/GPS/RTC/SD/IR/NVS validation claimed. |
| Board packaging | all eight final-source board builds, 32 artifact verification, version/partition/merge/config/link checks | Six enabled FSD boards; Classic/HackerBox zero FSD symbols/text/data/BSS. Eight sdkconfig files byte-identical to prior safety cycle. |
| Preserved feature boundaries | initial snapshot hash audit: display memory allocator, OUI/Observer, mdns/config/partition paths, untracked originals and symlink spelling | No claimed fix for unrelated clipping/size/option-gate findings; retained as backlog. |

## Independent integration review

All eight final-source packages independently validated at v3.0.19. The parent reran 674 regression tests (zero failures, one skip), real-LVGL UI fixtures, 10,000-request mailbox concurrency, mDNS allocation failures, USB stream/lifecycle and NTP/clock ownership tests. PC forward automation was corrected to use reviewed tile taps instead of direct function jumps; an explicit red/green regression demonstrates that distinction. These are host and package results, not physical acceptance.

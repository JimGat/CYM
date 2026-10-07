# v2.15.64: corrected #05/#06 integration

Co-developer @birolt29 supplied the no-PSRAM BLE-only table/wardrive-stack and
band-gating intent (#05), and Classic GPS route autodetection intent (#06).
Integration corrections/review used gpt-6.1-sol via openai-codex. Immutable
proposals were checked #05 then #06 in an isolated index, not committed as
unsafe raw intermediate versions. See .hermes/patch0506 for local evidence.

## Retained and corrected

- BLE dedup allocates lazily for BLE-only, with 128 internal entries on
  no-PSRAM targets. Capacity governs callback, flush and UI bounds; NULL/zero
  states, count and full-warning reset are guarded each session. Close the
  callback gate and await in-flight readers/host shutdown before freeing.
  Pending cleanup retains live memory instead of forcibly deleting it.
- Wardrive PSRAM stack is 8192 BYTES, internal fallback 4096 BYTES. Installed
  ESP-IDF 6.0 Xtensa and RISC-V StackType_t is uint8_t, not 32-bit words.
  No 16KB/32KB assertion is retained. Cooperative completion suspends the
  task before its observer deletes it/frees the static stack. Failed
  allocation/task/scan startup leaves a stopped dashboard. Physical
  high-water logs, not static locals or green links, must establish adequacy.
- NimBLE allocation ownership is tracked independently of synchronization.
  Installed nimble_port_stop waits forever for stop and event-loop handoff;
  it is not called on sync failure. A checked host task services the existing
  default event queue and asynchronous ble_hs_stop listener. Cleanup waits
  boundedly for scan worker and host acknowledgements before SDK deinit.
  Failed partial deinit blocks reuse instead of arbitrary restart/deinit.
  Compiled mocked cleanup tests exercise never-synced, pending, late-exit,
  concurrent-cleanup, worker-active, failed-deinit and repeated lifetimes.
  Source contracts additionally guard initialization and restart paths.
- Single-band targets show only 2.4GHz choices. No transport/payload changes.
- Classic GPS remains UART2/shared parser. Defer UART allocation until
  critical boot allocations complete and use one bounded nonblocking
  main-loop reader, not the early dedicated task that historically reset.
  GPIO1 RX remains the default. RF-HAT reserves GPIO22/27, so CN1 is skipped
  throughout. Without RF-HAT, RX22 is an input-only detection candidate.
  Never attach TX27 on absence; no Classic TX3/TX27, PCAS, PMTK or UBX writes.
  GPIO reset disables output; UART_PIN_NO_CHANGE is not a disconnect call.
  Driver initialization failures roll back ownership. Valid framed/checksummed
  NMEA survives split reads; configured/115200/38400/9600 are considered.
  Late detection and runtime receive baud/status update the GPS footer.
- P1 -> P3 follows co-developer-reported vendor silk; pin contract retained.
  His daily CN1 RX22/TX27 build is self-reported; his HAT RX1/TX3 route is
  schematic-derived, NOT hardware-tested by him. Jim's isolated test proved
  checksummed UART2 RX1 NMEA at 9600, not this production binary.
- Owner scoped GPS fixes ONLY to Classic CYD and HackerBox. Actual HackerBox
  build sdkconfig enables CYD2USB and inherits its UART/pins, with its own
  panel selector. Modern init/probe/checksum/send/rate/baud helpers were
  compared as preprocessed C tokens against a719a633 and remain identical.
  Generic BLE lifecycle changes from #05 remain shared. Rebuilt versioned
  images are not claimed byte-identical.

## Excluded/deferred

#04 is deferred entirely. Its supplied UI hunks are early-start cosmetic
repainting, not a separable timer-allocation/error-recovery fix. No legacy
spam/spoof transport, random-MAC rotation, spoof payload changes,
crash/SourApple enhancement, or newly enabled attack behavior was applied.
No RF transmission, flashing, device targeting, Doom/ESM work, stable/main
changes, tags/releases, beta-flasher edit, assets refresh or unrelated cleanup.

The alleged #05 wdp_ch_fail_logged reclaim is ABSENT from the original.
Current declaration is uint8_t[178], indexed by positive channels from the
existing channel tables (2.4GHz 1-14; 5GHz up to 177), guarded channel <178.
No reclaim was needed: all eight link. This array was left unchanged; no
integration-added memory shrinking is claimed.

## Qualification

All eight target build/package records, four-artifact SHA256s, descriptor
versions, linker section sizes and full logs are in the handoff. Classic
DRAM: .data 26675 B + .bss 96584 B = 123259 B; linker DRAM remainder 1321 B.
This is static-region headroom, NOT runtime free heap. Boot headroom and
internal BLE allocation remain hardware-dependent. The historical revert
4c8e248 and parent experiments are not declared root-cause-resolved.

Source tests and compiled UART/cleanup mocks are not physical concurrency,
radio or GPS proof. HAT/no-GPS boots, sustained reception, repeated benign
radio ownership transitions and stack high-water qualification are pending.

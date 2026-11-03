# HAT TX control (staged, not published)



@birolt29 supplied Package C's owner/stop-ack design origin and Package G's PN532
patch/native harness. JimGat separately owns the synchronized production state,
checked emitter integration, asynchronous UI/lifetime corrections and tests.
The preserved Package G evidence remains separate; combined-source gates must
replace G-only compiled acceptance. A is unchanged; B/D/E/F/H remain deferred.
No commits, pushes, Wiki publication or flashing are part of this procedure.

Only CC1101, nRF24, IR and RF433 transmit paths are controlled. Wi-Fi, BLE, AP,
802.15.4, utility traffic and NVS are not controlled. This is not a global RF
silence feature. Boot is ALLOWED, preserving baseline; state is runtime-only.

## Operator procedure (Classic and Modern)

1. Open a HAT screen (Radio, CC1101, nRF24, IR/LED/Universal Remote, TV-B-Gone or
   RF433). The middle topbar slot is labelled HAT TX. It preserves Home/Back,
   battery/GPS and Go Dark slots; the same control is used in both layouts.
   Long-press HAT TX to retain the existing screenshot action on supported boards;
   a long press does not toggle inhibition. Ordinary short taps control HAT TX.
2. Tap HAT TX while ALLOWED/ACTIVE. Expected: STOPPING while any admitted owner
   is pending; STOPPED only after every registered owner confirms checked stop.
   ERROR takes precedence when any stop failed. Receive-only/background users
   are not cancelled by this control; ordinary screen-navigation cleanup remains.
3. Tap an ERROR/STOPPING control to retry checked stops. Failed owners retain
   channels/pins/transaction payloads and refuse competing starts/shared-pin
   claims. A retry never clears ownership merely to make the UI look stopped.
4. Tap a fully STOPPED control to allow fresh starts. Expected: ALLOWED, not an
   automatic restart. Explicitly press a feature's Start/Send to transmit again.
5. Replay shows Transmitting until the asynchronous owner's real return. Sent
   means its software request/completion succeeded, not that a receiver heard it.
   Failures/cancellation are not reported as Sent. Universal search enables its
   success prompt only after actual software completion; departing invalidates
   pending labels/callbacks. Back/Home cancel without main-loop task joins.
6. If a competing HAT entry is refused, wait for the old owner to finish and
   explicitly retry. PN532 G retained-ownership refusal still precedes pin reuse.
   A reset starts a new runtime policy (ALLOWED), never a persisted inhibited
   state. Physical reset/reentry behavior needs bench validation.

## Admission, emission requests and quiescence are different

Tickets are registered before dispatching existing CC/nRF/TV/diagnostic tasks or
copied-signal replay jobs. Inhibition synchronously invalidates their generation;
removing inhibition cannot revive one. The independent owner/control service
performs checked stop; the main/UI loop does not join that owner. A request
already admitted at a racing call boundary can finish: do not describe inhibition
as a guarantee that no SDK/GPIO request can execute after the tap.

- CC1101: actual STX requests are admitted. Receive strobes are unchanged. Stop
  checks SPI success, MARCSTATE IDLE and GPIO-low result, retaining resources on
  failure. The historical 50 tick-rounded polls are not a 5/10 ms guarantee.
- nRF24: admitted CE-high sweep boundaries, including Blaster's nRF leg. Stop
  checks CE low and reads back CONFIG with PWR_UP cleared; standby is not used as
  proof of power-down. Receive scan/sniffer/Futaba owners retain their own guards.
- IR: at most an already admitted RMT frame may drain. RMT symbols are internal
  and retained until the installed SDK confirms transaction recycling. Timeout
  retains payload/channel ownership for explicit checked retry. LEDC stop errors
  are retained; stopping does not hide deinit/reinit or claim optical silence.
- RF433: replay cancellation is at a pulse edge, without truncating successful
  normal pulse widths. Timer callback admission cannot self-join esp_timer.
  Timer/GPIO stop errors and raw-diagnostic ISR removal errors retain ownership.

Loaded CC/RF timing entries must be nonzero and at most 30000 us; IR RMT entries
must fit 1..32767 us. Reject malformed/out-of-range data rather than truncate or
reshape it. Each decoded frame is at most 2 seconds; CC/RF repeat counts are at
most 20. Existing successful pulse widths/gaps are not replaced with cooldowns.

One lazily created 4096-byte internal owner stack/TCB services copied IR/RF jobs
and nonblocking stop requests. Control records and RMT payloads are internal;
decoded copies may use ordinary heap. Admission requires internal free >=16384
bytes and largest block >=6144 bytes. These are allocation safeguards, not
measured runtime headroom or task high-water proof. No broad task refactor.

## Software reproduction

Use fresh task-owned output paths on the canonical ESP32-Dev checkout:

    export IDF_PATH=/home/dev/esp/esp-idf
    python3 -B tests/run_regression.py --suite portable --suite sdk-native --output /home/dev/projects/your-task/new-output

Focused IDs: hat_tx, hat_emitters, hat_runtime, display_layout and the existing
four pn532 gates. Native tests execute production state, emitter requests/stops,
mailbox, epoch/cancellation and actual LVGL geometry. SDK/RTOS/GPIO endpoints are
synthetic. ASAN/UBSAN, synchronized pthread cancellation, stop-error retention,
stale starts, repeated toggles, mixed aggregate state and seven semantic mutants
are software evidence, not RF hardware qualification. The display harness covers
three panel geometries, all rotations and both navigation routes. Broader legacy
release checks, tracked-only portable export, nine-profile combined-source builds,
36 package artifacts and protected-input verification are separate final gates;
consult the task final-verification.json for actual executed results/counts.

## Unrun exact-board physical acceptance matrix

For each supported board/HAT route, record application SHA256, exact profile,
wiring, supply and scoped emission authorization. WS-S3-5B PN532 remains refused;
original NM no-card detection remains open. Do not substitute another profile.

    CC1101: RX baseline; replay/carrier/calibration start; inhibit during pulses;
      measured RF envelope/stop latency; MARCSTATE failure/retry; fresh restart.
    nRF24: RX scans/sniffer/Futaba preserved; sweep and Blaster nRF leg; CE and
      actual power-down; spectrum/stop latency; communication-error recovery.
    IR: normal remote/LED/Universal/TV sequences and LEDC jammer; optical capture;
      inhibit mid-frame; SDK-timeout retained payload recovery; receive reuse.
    RF433: normal pulse widths/repeats, jammer, raw GPIO diagnostic; inhibit in
      each phase; timer/low/ISR error retry and shared RX/PN532 transitions.
    Both layouts: keyboard/FSD/IR input responsiveness, Back/Home/reset/reentry,
      repeated toggles, stale completion refusal; no automatic resume.
    Memory: internal/DMA free minima/largest blocks, PSRAM, stack high-water and
      sustained repeated transitions with receive/shared-background users.

None of these physical checks was run. Physical RF/optical silence, electrical
compatibility and 5/10 ms stop guarantees are unmeasured. No Stable promotion is
implied. Parent owns independent acceptance, attribution-preserving commits,
publication/Wiki reconciliation and any separately authorized hardware work.

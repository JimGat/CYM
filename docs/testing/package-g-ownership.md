# Package G: PN532 retained ownership — v3.0.43 candidate

## Status and scope

This combined candidate preserves Package G and adds the separately documented
[Package C four-HAT control](package-c-hat-tx.md). Co-developer @birolt29 authored the
incoming handle-retention patch and native test. JimGat's integration corrections
separate readiness from ownership, add checked driver/manager release and propagate
refusal through six shared-pin claims. Package C's design originates with @birolt29; JimGat separately implemented its
production integration. There is no global/all-RF-silent claim. A is unchanged; B/D/E/F/H remain deferred.

Host tests and nine-profile compatibility builds are distinct from physical
acceptance. Consult the task's final-verification.json for actual executed results;
this text is not evidence that a build/physical check ran. Do not promote Stable,
publish a release or flash as part of these host procedures.

## Ownership contract

- Driver readiness requires complete bus+device ownership and completed init.
  First cleanup ends readiness, even if a release fails. A failed remove retains
  the device and bus; a failed delete retains the bus. New init first retries
  retained cleanup and refuses reacquisition while it still fails.
- `pn532_driver_release()` returns true only when both handles are gone.
  `pn532_driver_is_owned()` is not synonymous with `is_init()`. Call lifecycle
  APIs only under the serialized manager/UI owner after all users quiesce.
- `rfid_manager_release()` requests poll/emulation cancellation and returns false
  immediately while either worker still runs. It never force-deletes a worker,
  frees its card or releases its bus. A worker publishes completion after its
  last driver/callback access. Failed SDK cleanup retains buffers and ownership.
- Manager init retries pending cleanup instead of trusting its old initialized
  flag. Legacy stop timeout now retains the task; restart refuses replacement
  until it exits. Existing stop waits are not a new HAT inhibition implementation.
- IR, RF433, CC1101 and nRF24 claims, RF433 raw loopback and RF433 receive
  preparation check release even when manager init failed. A refusal returns
  before competing hardware configuration. The serial warning is
  `PN532 cleanup pending; shared pins retained`. Retry the explicit entry later;
  no automatic replay or new transmission is started by recovery.
- WS-S3-5B refuses PN532 admission before resetting native touch pads. This does
  not select a new S3 controller, add a route, alter pins or claim other boards'
  PN532 electrical compatibility. Original NM no-card detection remains open.

## Reproduce software gates

From the canonical checkout on ESP32-Dev, use a new output directory:

```sh
export IDF_PATH=/home/dev/esp/esp-idf
python3 -B tests/run_regression.py --suite portable --suite sdk-native   --output /home/dev/projects/your-task/new-regression-output
```

Expected: nonzero executed PASS entries, zero FAIL/NOT_RUN; private captures are
explicitly optional, not synthesized. Read results.json for exact counts. See
[tests/README.md](../../tests/README.md) for the four focused G IDs, dependencies,
mock boundaries and mutation semantics. A clean tracked-only export is a separate
portable check; warmed generated outputs are not a portable prerequisite.

## Exact-board physical checks (not run, no hardware permission)

For each hardware-supported exact board/HAT route, record profile, application
hash, configuration and wiring; do not substitute another board's image.

1. Enter RFID/NFC through the normal menu, then Scan & Read. Verify actual card
   detection/read against a known card; G does not promise to repair detection.
2. Stop, Back, Home, re-enter and repeat in Classic and Modern navigation. Verify
   CLI/FSD/IR input, Settings and normal keyboard responsiveness remain usable.
3. With scoped bench authorization and instrumentation, inject a recoverable I2C
   cleanup failure. Confirm the warning and blocked competing HAT entry; do not
   repurpose pins while cleanup remains pending. Clear the fault and explicitly
   retry. Verify teardown/re-init, no stuck bus and no stale worker/buffer access.
4. Test transitions RFID→IR capture/replay, RFID→RF433 receive/loopback,
   RFID→CC1101 RX/replay and RFID→nRF24 scan. No RF emission is authorized by this
   document; perform transmit checks only with separate appropriate permission.
5. Capture internal/DMA free minima/largest blocks, PSRAM and task high-water
   over repeated transitions. ELF deltas alone cannot prove runtime headroom.

Neighbor matrix: PN532 reader, card emulation, SAM retry, partial initialization,
IR/RF433 shared-pin reuse and receiver preparation, CC1101/nRF24 admission,
Classic/Modern routes, Back/Home/reentry, CLI/FSD and unchanged USB/GPS/time/SD/NVS
policies. Native extraction tests cover named boundaries, not all physical UI
transitions. Package G changes no display, stack, pin, partition or NVS policy. Package C
adds a narrow internal control owner task as documented separately.

## Attribution and publication handoff

Retain @birolt29's supplied patch as a separable human-authored contribution:
`@birolt29 <birolt29@users.noreply.github.com>`, committer JimGat. Its exact
SHA256 and the base→incoming→corrected maps live in the private task evidence.
Author subsequent readiness, manager, callers, tests and release corrections as
JimGat; do not falsely attribute those corrections or their hardware qualification
to @birolt29. Parent owns independent review, commits and publication. No AI
trailers or unpublished Wiki claims. Historical docs/accepted packages remain
historical; all nine development artifacts are the intended v3.0.43 cycle.

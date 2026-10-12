# CYM .84 responsiveness recovery implementation plan

> For Hermes: execute sequentially with one writer on ESP32-Dev. Jim approved the bounded diagnostic next step; do not introduce multi-agent review loops or a whole-app refactor. Parent independently verifies the worker handoff.

Goal: restore normal CYM response and display performance to at least the last demonstrably fast pre-.84 behavior, then improve isolated gameplay without regressing normal tools.
Architecture: keep CYM's existing LVGL menus, services and board adapters. Instrument only display/engine-I/O boundaries first. Restore efficient, independently owned DMA submissions with the smallest measured transport change. If necessary, replace only the isolated running-game LVGL presentation with a native panel/input loop; cold reboot returns to normal CYM.
Tech stack: existing ESP-IDF, FreeRTOS, LVGL 8, RGB565 SPI panel adapters, existing engine/PCM mailbox and host C/unittest harnesses.
Date: 2026-10-12. Authoritative source: /home/dev/projects/CYM-NM28C5-jarvis-ws35-docs on ESP32-Dev as dev, Jimgat_Dev. Baseline SHA: 44a57e051e8880d79611a8558880dc21a5166dcc (.86).

## Scope and alternatives
Recommended: measure boundaries, repair shared normal transport first, then conditionally isolate game rendering. This preserves the app and concentrates edits at existing display/storage interfaces.
Rejected: wholesale rollback to .83. That revives rejected-enqueue waits/private DMA allocation and abandons later fixes.
Rejected: whole-app display/service rewrite, global priority/tick changes, blind SPI/SD clock changes or another speculative stripe-capacity bump.
Allowed fallback: native rendering during isolated gameplay only; selector/license/normal menus stay LVGL. Do not implement this fallback in the first diagnostic candidate.

## Binding constraints
- Every source edit, test, build, package, commit and push executes on ESP32-Dev as dev. JARVIS VM is SSH orchestration only; no VM CYM clone or toolchain fallback.
- Check checkout/HEAD/status and competing processes before ownership. Preserve .hermes/, state_idf.ld, caches, docs/feedback/, docs/prompts/ and every unrelated change. No reset/clean/stash/unrelated staging.
- No main merge, tag, stable release, board flashing, partition/bootloader change, provider/runtime-setting change or protected-branch push.
- Preserve Deauth Monitor capture/Back behavior, Classic and Modern navigation, all orientations, startup SD consent, battery visibility/calibration and timekeeper fixes.
- Preserve independently owned aligned DMA memory, accepted-transfer ownership until true completion, safe rejected-enqueue behavior, fail-closed missing completion, watchdog protections, isolation/one-shot intent, audio and two-contact plus BOOT controls.
- No AI attribution or game name in commit messages; retain human co-developer credit/privacy.
- Read live AGENTS.md and canonical/release/shared-code rules. One shared patch version across all eight built boards; inspect actual packaged versions. Every affected board green before any push. Diagnostic delivery is Development/Beta only, not hardware acceptance.

## Established evidence and gaps
.84 replaced one panel draw per LVGL callback with separately commanded/staged/completion-waited stripes in both normal and isolated paths. .86 reduces stripes but remains serialized. Production 270-degree rotation maps a typical logical480x10 band to native10x480, not the host example480x15. Rotated callback shape must be recorded. Main priority1, engine2, PCM3 on unicore,100Hz; ISR already yields and mutex priority inheritance prevents a simplistic starvation conclusion. Isolated admission waits up to100x20ms per callback. panel_us includes admission; engine sd_us excludes admission/seek/tell; displayed counts canvas updates, not completed LCD frames. .86 supplied trace has normal280-399ms handler stalls, repeated isolated admission rejection and ~8s panel_us with zero successful callbacks. The vendor ST7796 driver discards underlying tx errors; handle this correctness issue separately and do not claim draw return proves enqueue on that driver.

## Task 1: preserve a traceable baseline (no old unsafe firmware flash)
Files/evidence: /home/dev/ws-c5-35-fixes/cycle87/ baseline.json, progress.md, remote report ../cycle87-investigation/report.md.
1. Read status/HEAD/rules and verify sole writer; save baseline tracked/untracked paths, all packaged versions, intended versions and SHA256 of each shipped boot/partition artifact.
2. Record existing physical .86 evidence and source-derived geometry as distinct evidence. Use .83/.80 source/history only as historical comparators; no unsafe rollback.
3. Archive meaningful gates in JSON; no secrets/private GATT fixture contents in reports.
Expected: preserved baseline and unmodified unrelated work.

## Task 2: test diagnostic accounting before instrumentation
Create: tests/test_cycle87_display_diagnostics.py. Create narrow helper if needed: ESP32C5/main/display_diagnostics.h (or existing suitable component; no broad framework).
1. Compile production helpers into a host harness, following tests/test_cycle84_dma_timekeeper.py and test_cycle85_startup_transport.py.
2. Inject controllable timestamps for bus admission, memcpy, draw return, real ISR completion and resumed task; distinguish accepted, rejected, delayed and missing completion paths.
3. Add native10x480 and all supported rotations/odd dirty widths. Test counter rollover and snapshot concurrency, geometries, zero-completion/rejected callback accounting and no ISR logging/allocation.
4. Initial test must fail for absent diagnostic behavior, then implement minimal helpers and rerun.
Expected: counters distinguish wall-time boundaries without changing transfers, waits or acknowledgement behavior. Do not fabricate hardware timings from mock clocks.

## Task 3: instrument shared display boundary without performance changes
Modify: ESP32C5/main/game_panel_transport.h; main.c on_color_trans_done, lvgl_flush_cb, normal handler and isolated main loop. Helper as above.
1. Use fixed bounded internal-RAM aggregates and a tiny bounded geometry sample set. No heap allocation, locks, I2C, serial logging or expensive atomics in ISR. Use an installed ISR-safe clock and lock-free32-bit stores; verify IRAM/data placement and task/ISR visibility. Do not introduce atomic64 library helpers or PSRAM-backed ISR state.
2. Capture callbacks/width/height/bytes/planned and accepted stripes, admission attempts/rejections and elapsed/max admission, copy, draw-call, completion wait; timestamp ISR immediately before give and resumed owner after successful take. Drain stale sem without corrupting sequence correlation. Mark samples that complete before draw returns; overlapping times must not be summed.
3. Separate normal and isolated phases. Periodic low-rate DISPLAY_DIAG output includes actual interval_ms, successful/rejected callbacks, completed stripes, geometry examples, summed/max boundary times and handler wall time. Logging only from task context after transfer/bus release, at most one compact summary per5s; no perstripe prints. Main starvation may delay reporting, so always print actual elapsed interval.
4. Record handler time and callback wall separately; residual is render/rotation/preemption wall-time, not CPU usage. Existing PERF names remain stable with documented semantics.
5. Keep stage4096, bus/wait budgets, panel clocks, priorities, audio, drawing and watchdog behavior identical to .86. The diagnostic candidate is observational, not an attempted fix.
Expected: actionable normal and isolated timings; no changed transport policy or unsafe ownership.

## Task 4: instrument engine I/O admission/hold separately
Modify: ESP32C5/components/cym_doom/doom_session.c and include/doom_metrics.h; bounded reporter in doom_ui.c if needed. Use an existing metrics helper instead of broad VFS abstraction changes.
1. Measure io_lock admission and hold for fread/fseek/ftell/open/close; count operation/read bytes and failure, include phase INIT versus RUNNING. Include bounded validation counters if necessary to disambiguate hash from engine I/O.
2. Preserve current I/O sequence, lock policy, cancellation, audio/write scheduling and frees. No fairness yield/priority change yet.
3. Report compact ENGINE_IO_DIAG with actual elapsed time and phase. Distinguish wait from hold and concurrent audio wall time. Sample task priority at reporting boundaries if the installed API can expose it; no guessed effective priority.
Expected: CPU/scheduler/mutex effects distinguishable from SPI wire time and storage hold time.

## Task 5: diagnostic build and delivery gates
1. Bump all three source PROJECT_VER files from verified maximum to next patch (.87 if .86 remains maximum) before changed native build. Update all eight manifests/memory docs via established workflow, label diagnostic in docs, preserve version format.
2. Run focused tests then full suite remotely: CYM_GATT23_FIXTURES=/home/dev/ws-c5-35-fixes/gatt23-private-fixtures PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests. Private fixtures stay private.
3. Freeze every actual source/build input including new helpers; . /home/dev/esp/esp-idf/export.sh; make all-boards. Save full logs and rc. Source changed after a successful native build requires next patch and rebuild; no hidden same-version candidate replacement.
4. Run scripts/verify-dev-packages.py --version <actual> --output <evidence>; independently check all eight app/full versions,32 artifacts, input drift and unchanged16 boot/partition artifacts. Scoped git diff --check excludes binary paths and preserves pinned upstream bytes.
5. Parent reviews actual instrumentation/ISR safety and independently verifies gates before scoped version-first diagnostic commit/push. Worker cannot commit/push. Parent runs exact-head CI/deployment and verifies liveBeta pin/eight versions, immutable hashes and stable/main unchanged. No stable promotion.
6. Deliver full-image immutable raw URLs, SHA256,offset0x0000, primaryUSB-C instructions and operator capture procedure to CLI and Telegram. Explicitly call it diagnostic, not restored performance.

## Task 6: capture discriminating hardware evidence
Start WS-C5-35, then WS-C5-28; user physically flashes, no remote flash authorized. Save complete serial logs including DISPLAY_DIAG, ENGINE_IO_DIAG and PERF.
1. Normal boot: do not start game or storage workers. Navigate same Classic/Modern Home -> Detect&Defend -> Deauth Monitor -> Back -> Settings/Hardware and compare portrait/landscape. Keep a quiet page for15s; record touch-to-visible response/video if practical.
2. Deauth Monitor: confirm scan/start/stop/capture path and safe Back; note render phases rather than treating monitoring success as UI success.
3. Isolated loading: capture hash/init phase and admission/hold geometry/timings. Failed display callbacks must be visible in counters, not silently classified as FPS.
4. After ENGINE_STARTED: collect60s steady gameplay, stationary then movement/firing/BOOT+touch, then Exit. Separate produced/canvas/completed-display counters. Actual complete-frame acceptance must not be inferred from a stripe or canvas update.
5. Parse all complete intervals with Python, weighted totals/counts and elapsed windows. Preserve startup and steady samples separately; compare on same board/settings/assets/workload. No need to flash known-unsafe .83 solely to obtain baseline.
Expected: dominant numerical bottleneck identified; physical input/UI remains mandatory acceptance.

## Task 7: targeted normal transport repair (only after Task6 evidence)
Touch only game_panel_transport.h/main flush and concrete affected adapter, plus tests. No menu/service refactor.
- If command/completion serialization dominates: restore one safely admitted color submission for a typical complete LVGL rotated band. Candidate: independently owned bus-aligned staging sized to the proven callback maximum and adapter single-transaction limit, or a validated direct path only when the actual source pointer/length is DMA-compatible and lifetime is owned. This is callback-sized admission, not arbitrary enlarging. Verify boot internal contiguous headroom under normal radio/services and avoid driver private allocation. Do not borrow draw buffers as staging because software rotation may use them as source.
- If draw/rotation residual dominates: narrowly eliminate redundant rotations/copies only at the flush integration boundary; preserve every orientation/color contract. No whole-app compositor rewrite.
- If bus admission dominates: bound render-owner blocking and restore retry/redraw semantics for safely rejected updates; a failed flush acknowledgement must not permanently lose dirty areas. Measure storage hold/admission before adding a local fairness mechanism. Do not bypass shared bus ownership or use unconditional priority boosts.
- Before using rejection safety, repair ST7796 tx error propagation with tests for each command/color failure, preserving no-borrow/partial-admission distinctions. No untracked vendor mutation or unsafe success assumptions.
For selected change: RED regression, minimal implementation, GREEN suite, new patch/eight-board cycle, physical same-workload comparison. One hypothesis per candidate.

## Task 8: conditional isolated gameplay bypass of LVGL
Authorized by Jim but not mandatory and not part of diagnostic candidate. Evaluate only after normal responsiveness is recovered and timings show game LVGL presentation dominates.
- Normal menus, selector and license remain LVGL. Isolated startup continues same-image reboot with consumed intent and normal_services=0.
- At running transition, main owner stops invoking gameplay LVGL rendering/timers cooperatively at a safe boundary, not while callbacks run. It owns panel presentation and direct touch/BOOT polling; engine still only publishes owned mailbox/snapshot data, PCM unchanged. Retain visible controls using fixed RGB565 assets/geometry without perframe LVGL redraw; native coordinates and orientation are explicitly tested.
- Do not call LVGL from engine/ISR or force-delete live tasks. Native presenter owns separate DMA buffers until real completion. Poll input independently of frame production/storage so Exit and movement/fire remain responsive. Budget partial updates versus frame viewport with measured display rate, not artificialFPS labels.
- Exit requests orderly cancel/audio stop; after ownership-safe completion, cold reboot to normalCYM. Never attempt live return to LVGL or repartition. Fail-closed reboot recovery may reset hardware; no reuse/free of live DMA or worker buffers.
- Native rendering does not solve shared SD contention by itself; retain measured, bounded bus arbitration. Test lifecycle/no-owner races and all two-contact/BOOT mappings before board builds.

## Acceptance and release gates
Normal CYM is first priority and can ship independently of gameplay improvement.
- Minimum: same-board/settings navigation and redraw no worse than the last defensibly fast pre-.84 reference; no visible slow painting, missing/skipped dirty regions, watchdog/crash/DMAallocation faults, or capture regression. If no timed safe baseline exists, Jim's physical usability acceptance and new timing measurements are mandatory.
- Proposed improvement targets (not promises or achieved results): ordinary navigation/Back visible response <=150ms typical; normal handler p95<=100ms under the controlled quiet menu workload, with SPI payload/render limits documented. Heavy storage provisioning is a separately qualified workload.
- Game: no seconds-long presentation/input starvation; aim >=10 completed visibleFPS over60s representative gameplay, at least recover earlier usable behavior, responsive movement+fire and Exit. If hardware limits prevent the aspirational target, report measured bottleneck and maintain an explicit experimental gate rather than call it publishable.
- Deauth Monitor still starts/stops/saves; startup SD consent and WS28 honest badge still work. AudibleSFX remains a separate physical gate.
- All affected builds/tests/packages green and exact remote deployment verification before test delivery; neither green builds nor nominalSPI clocks prove physical performance.

## Stop conditions and handoff
If remote host unavailable, competing writer present, ISR-safe clock unavailable, source freeze drifts, native headroom unsafe or diagnostic counters can't distinguish boundaries, stop with concrete blocker; never substitute a VM build or fabricated numbers. After diagnostic publication, wait for physical capture before speculative transport edits. No broad refactor, stable release or unrequested unrelated repair. Progress lives /home/dev/ws-c5-35-fixes/cycle87/progress.md; parent verifies actual diffs/tests/packages before publication.

## Task8 activation (cycle90, Jim-authorized following physical .89 evidence)

Jim reports normal .89 CYM responsive; PRESERVE that baseline. Task7 normal
repair is not required or activated. Game physical rejection (.3fps) plus
cycle90/hardware-game-89-analysis.json justifies Task8 isolated native RUNNING
and the game-only main-owner priority3/fairness boundary. No second method
approval, whole-app refactor, global priority/tick/SPI change or init-fairness
experiment. See docs/isolated-native-presentation.md for implemented scope and
truthful completion counters. Eight-build/parent-review and physical acceptance
remain required; this activation is not a claim of >=10FPS or audible SFX.

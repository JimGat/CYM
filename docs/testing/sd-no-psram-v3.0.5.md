# v3.0.5 Development: SD provisioning qualification

## Scope and evidence boundary

Co-developer @birolt29 supplied Patch #11. Immutable input SHA-256:
`d0985bf4a2b5563b3ee972f2fbca8fc35227dfda36dcfb3497c744ca50eebc79`.
The accepted capability makes automatic provisioning available without PSRAM.
Corrections retain runtime registered-total-SPIRAM allocation selection, prevent
internal fallback on PSRAM OOM, fix the 16KB claim to **4096 bytes**, and add safe
worker ownership, pre-format resource checks and truthful failure reporting.
All 61 existing SD_ITEMS and native display/touch/console/GPS paths are retained.
Stable remains v3.0.2; this document is Development-only, not a release approval.

A worker is statically created on the main task core. At completion it records
its fixed-size result and high-water reading, removes its watchdog subscription,
and suspends itself. Main (CPU0 on all eight build profiles) waits for eSuspended,
then deletes the non-running task before freeing its stack and queue. Installed
IDF non-running vTaskDelete invokes prvDeleteTCB synchronously; statically owned
TCB/stack storage is not freed by that function. No self-stack free, early done
flag, live TCB reuse, WithCaps cleanup helper, summary malloc or worker LVGL
callback is used. Leaving the page clears LVGL pointers; main still cleans up,
and new work cannot start until cleanup finishes. Cleanup waits for main to run;
there is no claim of immediate reclamation at the final filesystem operation.

Native production-source extraction checks exercise allocation class, injected
stack/queue/task failures, repeated-run resource balance, delayed suspension,
I/O and format failures, status/Back recovery and deleted-screen completion.
The real LVGL consent/modal test covers six geometries and PSRAM present/absent.
These are software checks, not measured physical timing, stack headroom or heap.
Jim accepted both v3.0.4 Classic/HackerBox landscape builds; this is not acceptance
of the new v3.0.5 provisioning code or every detailed v3.0.4 checklist item.

## Owner operator checklist (not performed by the build worker)

1. Use each board matching v3.0.5 Development package without erasing NVS/user
   data. Start with Classic CYD and HackerBox (no PSRAM), then a PSRAM board.
   Keep console/GPS wiring unchanged; never attach log output to GPS UART.
2. Prepare a backed-up FAT32 test card with missing feature folders. Boot through
   touch calibration and home-layout choice first. Expect Later / Provision.
   Choose Later: no worker and no provisioning writes. Reboot and explicitly
   choose Provision: expect deferred startup and eventual truthful result.
3. Classic Settings → SD Card; Modern Tools → Settings → SD Card. In each layout
   run Validate & Provision on missing items, then again on a complete card.
   Expect missing entries created, existing file hashes unchanged. Back becomes
   enabled when done. Existing directories and seed contents must survive.
4. Run at least ten times, allowing main-context cleanup after each. Record
   internal/PSRAM free heap, largest blocks and minimum free heap before/during/
   after; distinguish LVGL page allocation from worker memory. Expect bounded
   resources and no monotonic worker stack/queue leak, crash or stalled UI.
5. Capture `[SD_PROV]` stack high-water logs (bytes; depth 4096) on no-PSRAM and
   PSRAM boards, with representative cards and both orientations. Assess real
   minimum margin; no adequate-headroom claim is made by compile/native tests.
6. In a controlled low-memory diagnostic, force queue/stack/task-start failure.
   Expect Failed (not Running or Done), usable Back, OK-only manual SD popup,
   no validation-success claim, and no filesystem writes/format. On a PSRAM board
   exhaustion must not silently use an internal stack. Manual fallback copies
   `CYM-SD-Assets/sdcard/` contents to root while preserving user files.
7. On a backed-up disposable card ONLY: refuse each Format + Provision confirmation
   separately; expect no formatting. Explicitly accept both to test the destructive
   path. No format may start before worker resources exist. Induce I/O/format/
   remount failure safely: expect Failed, not a green 0-item success. Partial work
   or changed files may exist after a started operation; inspect the card.
8. Leave via top-bar Back/Home while running, then revisit after completion.
   Expect no callback into deleted objects, no stale completion on a new page,
   and bounded cleanup. Check native panel orientation/touch, existing GPS,
   primary console, RGB and Go Dark remain unchanged. Preserve serial/screens
   and exact board/version/layout/orientation in the owner acceptance report.

No real hardware was flashed, formatted or tested during implementation/build.

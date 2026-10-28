# FSD remote USB UI — Development v3.0.19

**Current release:** included in Stable v3.0.27 on console-capable release boards. The maintained PC script still reports 3.0.19 (script version, not firmware version). Development references below describe its introduction; physical/native-Windows acceptance limits remain unchanged.

FSD is included in **normal console-capable Development firmware**, not a separate
test image. Co-developer **[@birolt29](https://github.com/birolt29)** contributed
Patches #13 (Windows builds), #14 (Back navigation) and #15 (FSD and PC driver).
The integration adds UI-owner dispatch, bounded request lifetime, strict framing
and a fail-closed PC route policy. The single maintained PC script is
[`tools/fsd.py`](../../tools/fsd.py), version **3.0.19**. Earlier supplied copies
are not the maintained protocol implementation.

FSD exposes powerful local USB controls. Manual navigation/taps can start radio
tools, transmit, or change settings. Use only your own authorized laboratory
hardware and controlled RF environment. There is no remote authentication layer;
physical USB access is the trust boundary. This work did not connect, flash or
operate any board, validate RF behavior, or validate GPS operation.

## Patch #20 additions - Development v3.0.40

HOST software owns run/route consent and authorization. Firmware adds no new
consent prompts or blanket automation restrictions; existing dark/dim/lock/
settling, physical-input and exclusive-screen ownership guards remain effective.
The pre-existing Python driver's own safe route policy is unchanged.

On an authorized host console (not executed by this integration):

```text
where
  where depth=<N> back_fn=<name> stack=[...] orient=<L|P> layout=<C|M>
tree
  <<<TREE>>> ... object records ... <<<ENDTREE>>>
tap 40 60
  tap ok
swipe 100 180 -100
  swipe ok
```

Coordinates/deltas are logical pixels. Tree flag `S` means scrollable. `where`
includes firmware orientation and layout; maintained Python client accepts its
unchanged prefix and retains raw tree output. No PC API rewrite/swipe helper added.

`tap ok` / `swipe ok` means final sample consumption, NOT proof of a widget hit,
destination, completed action or authorized use. Validate with `where`, `tree`,
`shot` and application status. Normal final-release navigation is valid. Console
waits for asynchronous UI completion; UI never waits for drain.

Pending samples abort on caller cancellation, armed deadline, page/rotation/
geometry change, physical collision or existing locks. Errors describe `gesture
cancelled`, `gesture deadline expired`, `gesture page or rotation changed`,
`gesture input locked or settling`, `gesture interrupted by physical touch`, or
`input locked, settling, or physical touch active`. Inspect effects before retry:
earlier samples may already change selection/scrolling. Never blindly retry after
transport timeout. Ownership remains busy until real consumption/cancellation.
A colliding finger is suppressed until real release; nonphysical cancellation
adds no retry cooldown. Dropdown transient overlays remain valid.

No new sleep/drain wait/debounce/timer throttle/keyboard delay or ordinary-touch
tree scans. Idle work is constant-time; native timings are not hardware latency.
BT Observer changes normal UI in BOTH Classic and Modern, even console-disabled:
function_page parent, 18x18 y=32, list rebuild survival and stop/Back/Home teardown.

Remaining exact-board hardware acceptance: ordinary finger/navigation/keyboard
responsiveness in both layouts and supported rotations; tap/swipe/dropdown,
cancel/deadline/late-release, physical collision, page/rotation ownership, no
phantom clicks/stuck press and retry; Observer rebuild/Back/Home/reentry; existing
RF-HAT/display/SD gates. Builds/sanitizers do not qualify physical behavior.

## Boards and orientation

| PC board argument | PSRAM | Logical UI at profile default | FSD rotation |
|---|---|---|---|
| `nm-cyd-c5` | 8 MB | 240×320 | Existing 0/90/180/270° contract |
| `ws-c5-28` | 8 MB, including owner-confirmed v3.0.18 hardware | 240×320 | Existing 0/90/180/270° contract |
| `ws-c5-35` | 8 MB | 320×480 | Existing 0/90/180/270° contract |
| `pancake-c5` | 8 MB | 480×320 | Fixed profile; unsupported |
| `hosyond-s3-35` | 8 MB | 320×480 | Fixed S3 profile; unsupported |
| `ws-s3-5b` | 8 MB | 512×300, scaled to physical 1024×600 | Fixed S3 profile; unsupported |
| `cyd-2432s028` | No PSRAM | 240×320 | **No FSD: console-none unchanged** |
| `hackerbox-cyd` | No PSRAM | 240×320 | **No FSD: console-none unchanged** |

These are source/profile capabilities, not fresh hardware qualification claims.
Pancake-C5 and WS-S3-5B remain Development-only experimental targets. FSD creates
no new board orientation support. A screenshot is the LVGL logical rendering,
including the top overlay, not a camera image or a capture of the panel bus,
backlight, physical scaling, color wiring or touch calibration. Screenshots alone
do not prove a display works. Both Classic and Modern Home layouts are supported;
choose the desired layout manually before each run. The script never changes or
saves layout preferences.

## Install one maintained script

Run from a CYM checkout on the operator computer. These commands install Python
packages on that computer only; they do not flash firmware.

```sh
python3 -m venv .venv-fsd
. .venv-fsd/bin/activate
python -m pip install pyserial Pillow
python tools/fsd.py --version
# Expected: 3.0.19
python -m serial.tools.list_ports -v
```

Windows PowerShell equivalents (native Windows execution still requires testing):

```powershell
py -3 -m venv .venv-fsd
.\.venv-fsd\Scripts\Activate.ps1
python -m pip install pyserial Pillow
python -m serial.tools.list_ports -v
python tools\fsd.py --version
```

Connect the board's **primary USB-C console** and explicitly select its port
(e.g. `/dev/ttyACM0`, `/dev/cu.usbmodem...`, or `COM5`). Speed is **115200**.
Do not use GPS UART pins, another header, or the host computer's unrelated serial
port. Close other serial terminals first. The firmware keeps its existing USB
console routing; FSD does not reroute UARTs. The script does not request a board
reset, toggle DTR/RTS, flash, erase, or forward GPS. An OS/USB driver may still
have connection side effects; verify your board behaves normally when opened.

Opening the port begins an append-only raw capture for that run. There is no
input-buffer reset. Existing boot/crash text must not be discarded to make a run
appear successful.

## Operator-prepared safe PC suites

1. Manually stop any radio/tool activity using its normal controls.
2. Return **Home**. Dismiss startup prompts manually only after reviewing them.
3. Select Classic or Modern layout manually. Leave no modal/popup visible.
4. Close the terminal and run one reviewed route with the explicit port.

```sh
# Home-only: where + heap + actual screenshot + tree, no menu traversal.
python tools/fsd.py ws-c5-28 smoke --port /dev/ttyACM0

# Classic layout: tap Settings, then normal Back to Home.
python tools/fsd.py ws-c5-28 path Settings --port /dev/ttyACM0

# Modern category path, then Back twice; select Modern manually first.
python tools/fsd.py ws-c5-28 path 'Tools & System>Settings' --port /dev/ttyACM0

# Review this menu only, not every child tile.
python tools/fsd.py ws-c5-28 menu 'Tools & System' --port /dev/ttyACM0
```

PowerShell uses e.g. `--port COM5` and quotes `'Tools & System>Settings'` similarly.
Reviewed routes are only Home, Settings, Tools & System, and
Tools & System → Settings. The entire route is checked **before serial opens**;
other scopes fail closed. The script taps the reviewed visible labels through `tapt`, then uses the normal top-Back path. It never uses direct `nav` jumps to substitute for missing tiles. Select Classic for the Settings route and Modern for Tools and System routes; a missing tile or unexpected destination fails the run. The route allowlist bounds automated scope, but host/source review is not physical proof of radio inactivity. Unknown initial state aborts rather than attempting escape. The script never presses an affirmative popup button, auto-dismisses warnings, visits arbitrary child tiles, or automates a transmitting run.

Expected progress is `PASSED <action>` only after all of:

- `where` reports the exact expected stack **and depth**;
- `heap` returns actual internal/DMA/PSRAM readings;
- `shot` returns a complete valid image, which is saved as a PNG;
- no captured crash marker or serial reader error is present.

A `menu` run records unreviewed child tiles as **SKIPPED**, never as tested.
Unsupported boards/operations are distinguished from missing-command/timeout
failures. Exit code 0 means the implemented suite passed; 1 is runtime failure;
2 is rejected/unsupported input. No screenshot is synthesized or padded. A crash
marker anywhere in the continuous run capture stops the run, including an old
boot crash observed before its first command.

Artifacts are next to the maintained script:
`tools/fsd-runs/<UTC timestamp>_<board>_<suite>/`:

- `serial.raw`: continuous received bytes, including crash/debug text;
- numbered PNGs: actual decoded complete logical frames only;
- `report.json` and `report.txt`: expected/observed destinations, actual heap
  readings, deltas from the initial step, failed/unsupported/skipped steps.

Raw logs/screenshots can disclose Wi-Fi names, GPS coordinates, storage paths or
other private data. Review and redact copies before sharing; preserve original
crash evidence privately. Do not publish whole run directories blindly.

## Manual USB command reference

Use a serial terminal at 115200, or `python -m serial.tools.miniterm PORT 115200`.
The responses below describe the protocol, not physical-board results from this
integration. `help` still lists the existing debug-console commands plus FSD.

| Ask / command | Expected response / meaning |
|---|---|
| `where` | `where depth=N back_fn=set\|none stack=[...]`; Home is depth 0, empty stack |
| `heap` | `HEAP internal_free=... internal_largest=... internal_min=... dma_free=... dma_largest=... psram_free=... psram_largest=...` (bytes) |
| `tree` | `<<<TREE>>>` through `<<<ENDTREE>>>`; current IDs, depth, class, flags, logical position/size and text |
| `shot` | `<<<SHOT w=W h=H fmt=rgb888>>>`, exactly one `SHOTROW y=Y data=<base64>` per row, then `<<<ENDSHOT>>>` |
| `nav Settings` | `nav ok`, then inspect `where`; direct function jump, **not** a tile click |
| `nav Tools & System` | `nav ok`; exact screen names, unknown names fail |
| `back` | `back ok`; normal deferred Back/stop path; inspect `where` afterward |
| `tapt Settings` | `tapt ok id=N: Settings`, or an explicit miss/error; label comparison case-insensitive, newline normalized to space |
| `tap 50 70` | `tap ok` only for an eligible logical hit target; coordinates must be within the current logical display |
| `tapid 12` | `tapid ok`; use a fresh tree ID, which is volatile across rebuild/navigation |
| `move 12 20 40` | `move ok`; volatile logical screen-position preview, layouts may reposition it |
| `size 12 90 35` | `size ok`; volatile size preview, no source/NVS update |
| `text 12 Preview` | `text ok`; label or first label child, maximum 95 UTF-8 bytes, no silent truncation |
| `rotate landscape` | `rotate ok` only on existing supported orientation boards; returns Home; no NVS save |
| `rotate 0` | Restore 0° through the existing supported board contract; S3/Pancake report unsupported |

`tap`, `tapid`, `tapt`, arbitrary `nav`, and widget edits are **manual powerful
controls**, not covered by the PC safe-route guarantee. They can start features,
transmit, alter live settings, or make controls unreadable. Do not use them as an
unattended fuzzer. Disabled/hidden controls are not eligible tap targets. A
visible modal blocks access to underlying screen controls; manually operate the
popup only after reviewing it. Synthetic clicks stop immediately if a handler
deletes the object. They are not physical touch calibration/drag tests.

Numbers are fully validated: suffixes, overflow, out-of-range values and excess
arguments fail. Labels longer than the request bound fail; tree labels abbreviated
with `~` are explicitly incomplete. Tree output is bounded to 24 KiB / 64 levels and excessive
trees return an error rather than a fabricated complete tree. Screenshots require
PSRAM and bounded logical dimensions (up to 800 per axis, at most 640,000 pixels);
allocation failure is reported. RGB565 is converted to framed RGB888. PC decoding
rejects missing/duplicate/out-of-order rows, invalid base64, wrong byte counts,
absent terminators or dimensions beyond the bound. Interleaved normal logs are
retained in `serial.raw`; a damaged image row fails instead of being guessed.

## Debug policy, timeouts and recovery

FSD does not change the persisted debug/log policy, globally mute logs, restore
an arbitrary INFO level, or clear crash evidence during screenshots. Debug output
can interleave with framed images. If it corrupts a row, the capture fails; keep
the raw log and retry after inspecting the cause rather than suppressing crashes.
The existing `debug` settings and console worker remain intact. If optional FSD
command registration fails, its partial registrations are removed and the
accepted debug console is preserved; check boot logs for `FSD unavailable`.

Only the UI-owner main loop, while holding its normal LVGL mutex and outside LVGL
callbacks, dispatches requests. No cross-task `lv_async_call` is used. One bounded
request can be outstanding. There are no new FSD tasks or persistent semaphores.
Requests and tree/image/transport buffers use PSRAM without an internal fallback;
LVGL's own snapshot scratch follows its existing allocator policy. Command
registration has an additional persistent allocation cost in the IDF console.
Do not interpret idle firmware size or host tests as live SRAM headroom proof.

The firmware wait is bounded to five seconds. A timed-out request that has not
started is cancelled; an already-running operation has an **indeterminate
outcome**, so do not automatically resend a tap/navigation command. Caller and
UI-owner each hold a reference; buffers remain owned until the last participant
finishes. A late completion cannot overwrite a newer request. If the UI owner is
stalled, the single request remains bounded/owned and later commands return busy
until it drains. Wait, inspect `where`/`tree`, and recover manually. Report a
persistent stall with the raw log. A screenshot transfer itself can take longer
than the UI request; the PC permits up to 60 seconds for the framed transfer.

## Validation boundaries and next checks

Host regressions exercise production parser/navigation/lifetime functions and
real LVGL with synthetic SDK/transport fixtures; they are not device evidence.
Native Windows execution with Windows binutils and physical USB/board testing remain pending.
For each supported board and both layouts: record boot/version/PSRAM, USB command
registration, raw logs, Home→reviewed menu→Back, exact stack, real screenshots,
logical/panel comparison, overlays, object-deleting callbacks, deliberate timeout
then recovery, and long-lived internal/DMA minima before/during/after captures.
Verify debug settings remain unchanged and no new radio activity occurs in the
menu-only route. Classic/HackerBox must retain console-none/no FSD behavior.

Keep the WS-C5-28 Clock/NTP-first path, 4096-byte **internal** mDNS stack, and
internal RTOS controls unchanged. The reported internal allocation failure remains
**OPEN**; PSRAM capacity and a static linker delta do not resolve fragmentation.
Do not move the stack to PSRAM, shrink it, or free live task resources as an FSD
workaround. OUI caching and Bluetooth Observer retention need separate measured
lifetime evidence before any optimization claim.

GPS/NMEA USB passthrough/relay is a **future proposal only**. This implementation
does not forward NMEA, alter GPS UART routing or enable radio automation. UI
observations such as clipping, tile size or a hardware-option gate belong in the
backlog unless separately approved, not silent unrelated fixes in this patch.

See [memory impact and related-function regression checklist](fsd-memory-impact-v3.0.19.md) for measured target sizes, persistent costs and pending physical checks. The maintained bounded driver currently produces PNG/JSON/text artifacts; the original unrestricted menu sweep and GIF option are not part of these qualified suites.

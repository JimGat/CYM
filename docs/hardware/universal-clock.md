# Universal Clock Operator Guide

The Clock feature is available in both Classic and Modern navigation on every released CYM target:

- WS-C5-28
- NM-CYD-C5
- CYD-2432S028
- Hosyond ES3C35P

Open **Clock** and choose one operating mode. The mode is not saved as a boot default.

## Display Only

Use **Display Only** when the board must remain offline.

Expected behavior:

- The screen does not start Wi-Fi station mode.
- The screen does not start an access point.
- The screen does not query public NTP.
- It displays the best already-trusted UTC source: qualified GPS, a valid RTC, or RTOS holdover from an earlier accepted GPS or public-NTP update.
- If no trusted source exists, the source badge reads `UNSYNCED` and reliability reads `Untrusted`.

## Client NTP

Use **Client NTP** to explicitly permit Wi-Fi and a bounded public request to `pool.ntp.org`.

Expected behavior:

- If station connectivity is unavailable, Clock uses the existing Data Transfer credential workflow.
- Each public synchronization attempt is bounded to approximately five seconds.
- While Client NTP remains selected and GPS is not locked, Clock retries public NTP every 60 seconds.
- A successful update disciplines the RTOS system clock on every board and resets source age and uncertainty.
- On WS-C5-28, the PCF85063A RTC is repaired only when absent, invalid, untrusted, or at least five seconds wrong.
- Qualified GPS supersedes public NTP and suppresses periodic network polls; polling resumes after loss of lock.
- One failed refresh preserves explicit `NTP HOLDOVER` lineage instead of presenting a recently synchronized clock as generic red RTOS holdover.
- Failure retains any trusted local source and does not turn a stale or absent time into a false synchronized state.

## AP NTP

Use **AP NTP** to serve local UTC without requiring Internet access.

Expected behavior:

- The board creates a protected `CYM-NTP-xxxxxx` access point.
- The dashboard displays the AP address and credentials.
- The board serves UDP/123 from the best trusted local source.
- If no trusted source exists, replies use NTP leap-alarm and stratum 16; they do not claim synchronized time.

## GPS RTC Holdover

Some UART GPS modules, including ATGM336H-class devices, continue emitting UTC date and time in RMC sentences while navigation status is void (`V`). Clock treats that stream as a possible module RTC, not as satellite lock:

- Three consecutive, monotonic no-fix samples are required before consideration.
- The module RTC must first be cross-validated within five seconds of public NTP or a real active (`A`) GPS lock.
- A validated module may later appear as amber `GPS RTC HOLDOVER`; it never appears as green `GPS LOCK` without an active satellite fix.
- Trust is retained across restart, but a discontinuity or time earlier than the last trusted epoch revokes it until another NTP/GPS cross-check.
- Fresh public NTP, qualified GPS, and a trusted fitted board RTC remain preferred sources.
- Module-RTC trust persistence is deferred to the internal-RAM main task; the PSRAM-backed GPS task does not write NVS.

## Source progression

1. `GPS LOCK` after three consecutive valid active-fix samples.
2. `PUBLIC NTP` after a successful Client NTP poll; nominal refresh is every 60 seconds.
3. `RTC HOLDOVER` where a trusted fitted RTC is available.
4. `GPS RTC HOLDOVER` when a no-fix GPS-module clock was previously cross-validated and remains monotonic.
5. `NTP HOLDOVER` or `RTOS HOLDOVER` when only the disciplined system clock remains.
6. `UNSYNCED` when no trusted source exists.

## Reliability and uncertainty

Clock reports both a qualitative level and a conservative uncertainty:

- `Excellent`: qualified GPS with low estimated uncertainty.
- `Good`: fresh accepted public NTP, or another trusted source below the Good threshold.
- `Holdover`: trusted fitted RTC, cross-validated GPS-module RTC, or explicit NTP holdover.
- `Degraded`: trusted time with a larger uncertainty estimate.
- `Untrusted`: no accepted time source.

Uncertainty grows with source age using the selected board profile. The dashboard also reports source age, RTC capability, GPS-UART capability, and whether the estimate is characterized.

When a live GPS fix is available, the Clock displays a six-character Maidenhead locator (`Grid: EM12ab`) directly below the date. The grid is calculated locally from latitude and longitude without Internet access. Without a fix it displays `Grid: waiting for GPS fix`; boards without GPS-UART capability display `Grid: unavailable`.

**Timing values are conservative uncharacterized engineering estimates, not measured accuracy.** Compilation validates software integration only; it does not physically characterize oscillator drift, RTC persistence, GPS transport delay, network accuracy, or NTP-client interoperability.

## Board profiles

| Board | RTC | GPS UART | RTC drift allowance | RTOS drift allowance | Base GPS estimate | Base public-NTP estimate | GPS-module RTC estimate |
|---|---:|---:|---:|---:|---:|---:|---:|
| WS-C5-28 | PCF85063A | Available | 50 ppm | 100 ppm | ±500 ms | ±250 ms | ±2 s + 100 ppm |
| NM-CYD-C5 | Not fitted | Available | n/a | 100 ppm | ±500 ms | ±250 ms | ±2 s + 100 ppm |
| CYD-2432S028 | Not fitted | Not supported | n/a | 150 ppm | n/a | ±250 ms | n/a |
| Hosyond ES3C35P | Not fitted | Available | n/a | 100 ppm | ±500 ms | ±250 ms | ±2 s + 100 ppm |

All values in this table are deliberately conservative engineering allowances and remain unqualified until measured on hardware.

## Time semantics

- RTC, GPS, RTOS system time, public NTP, and served NTP are UTC.
- The Clock Settings UTC offset changes presentation only.
- Clock brightness is independent of general screen brightness while Clock is active.
- Display Only does not initiate recovery. Select Client NTP when an explicit network recovery is wanted.


## off-grid FT4/FT8 GPS time service

Time-synchronized amateur-radio modes such as FT4 and FT8 are a primary AP NTP use case. With a UART GPS receiver and qualified `GPS LOCK`, CYM can provide local UTC to an isolated radio computer without Internet or cellular coverage. Join the displayed `CYM-NTP-xxxxxx` network and configure the client to use the displayed address, normally `192.168.4.1`.

The WSJT-X User Guide says the computer clock should be synchronized to UTC within about one second.[3] CYM's on-screen source, age, reliability, and conservative uncertainty are the operator's go/no-go indicators.

The present implementation timestamps UART RMC data and has no GPS PPS input. It is not Stratum 1. Favorable receivers may produce sub-50-ms results, but the system is not characterized or calibrated to that level and is **not a guaranteed sub-50-ms** source.

## Accuracy and suitability grid

| Source/state | Base allowance | Growth allowance | Practical guidance |
|---|---:|---:|---|
| Qualified UART GPS lock | ±500 ms | Requalified by RMC | Expected to fit normal FT4/FT8 timing while trusted; no PPS guarantee |
| Fresh public NTP | ±250 ms | Converts to NTP/RTOS holdover | Good recovery source where Internet exists; asymmetry matters |
| WS-C5-28 PCF85063A RTC holdover | Last disciplined UTC | 50 ppm = about **4.32 seconds/day** | Battery-backed continuity; resynchronize after long outages |
| C5/S3 RTOS holdover | Last disciplined UTC | 100 ppm = about 8.64 seconds/day | Short outages only for timing-sensitive modes |
| Classic CYD RTOS holdover | Last disciplined UTC | 150 ppm = about 12.96 seconds/day | Least predictable profile; no supported GPS UART |
| Validated GPS-module RTC | ±2 s | 100 ppm = about 8.64 seconds/day | Continuity only; never presented as GPS lock |
| `UNSYNCED` | Unknown | Unknown | Do not use as a timing authority |

## WS-C5-28 RTC reliability

The WS-C5-28's PCF85063A can preserve UTC from its backup supply, but the IC depends on an **external 32.768 kHz crystal** rather than an atomic or temperature-compensated reference.[2][4] Real drift depends on the crystal's initial tolerance and temperature curve, PCB capacitance/layout, aging, offset calibration, battery health, and holdover duration.

The PCF85063A has an offset-calibration register, but CYM does not currently characterize each board or automatically calibrate it. The firmware therefore uses a conservative 50-ppm allowance—about 4.32 seconds/day—and labels it uncharacterized. That does not assert every unit drifts by that amount; it avoids promising better before physical soak data exists.

Sources:
[2] https://www.nxp.com/docs/en/data-sheet/PCF85063A.pdf — NXP PCF85063A data sheet
[3] https://wsjt.sourceforge.io/wsjtx-doc/wsjtx-main.html — WSJT-X User Guide
[4] https://docs.waveshare.com/ESP32-C5-Touch-LCD-2.8 — Waveshare ESP32-C5-Touch-LCD-2.8 documentation

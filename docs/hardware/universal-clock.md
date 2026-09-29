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
- The public synchronization attempt is bounded to approximately five seconds.
- A successful update disciplines the RTOS system clock on every board.
- On WS-C5-28, the PCF85063A RTC is repaired only when absent, invalid, untrusted, or at least five seconds wrong.
- Qualified GPS may supersede public NTP.
- Failure retains any trusted local source and does not turn a stale or absent time into a false synchronized state.

## AP NTP

Use **AP NTP** to serve local UTC without requiring Internet access.

Expected behavior:

- The board creates a protected `CYM-NTP-xxxxxx` access point.
- The dashboard displays the AP address and credentials.
- The board serves UDP/123 from the best trusted local source.
- If no trusted source exists, replies use NTP leap-alarm and stratum 16; they do not claim synchronized time.

## Reliability and uncertainty

Clock reports both a qualitative level and a conservative uncertainty:

- `Excellent`: qualified GPS with low estimated uncertainty.
- `Good`: fresh accepted public NTP, or another trusted source below the Good threshold.
- `Holdover`: trusted RTC or RTOS holdover whose estimate is still within the holdover threshold.
- `Degraded`: trusted time with a larger uncertainty estimate.
- `Untrusted`: no accepted time source.

Uncertainty grows with source age using the selected board profile. The dashboard also reports source age, RTC capability, GPS-UART capability, and whether the estimate is characterized.

When a live GPS fix is available, the Clock displays a six-character Maidenhead locator (`Grid: EM12ab`) directly below the date. The grid is calculated locally from latitude and longitude without Internet access. Without a fix it displays `Grid: waiting for GPS fix`; boards without GPS-UART capability display `Grid: unavailable`.

**Timing values are conservative uncharacterized engineering estimates, not measured accuracy.** Compilation validates software integration only; it does not physically characterize oscillator drift, RTC persistence, GPS transport delay, network accuracy, or NTP-client interoperability.

## Board profiles

| Board | RTC | GPS UART | RTC drift allowance | RTOS drift allowance | Base GPS estimate | Base public-NTP estimate |
|---|---:|---:|---:|---:|---:|---:|
| WS-C5-28 | PCF85063A | Available | 50 ppm | 100 ppm | ±500 ms | ±250 ms |
| NM-CYD-C5 | Not fitted | Available | n/a | 100 ppm | ±500 ms | ±250 ms |
| CYD-2432S028 | Not fitted | Not supported | n/a | 150 ppm | n/a | ±250 ms |
| Hosyond ES3C35P | Not fitted | Available | n/a | 100 ppm | ±500 ms | ±250 ms |

All values in this table are deliberately conservative engineering allowances and remain unqualified until measured on hardware.

## Time semantics

- RTC, GPS, RTOS system time, public NTP, and served NTP are UTC.
- The Clock Settings UTC offset changes presentation only.
- Clock brightness is independent of general screen brightness while Clock is active.
- Display Only does not initiate recovery. Select Client NTP when an explicit network recovery is wanted.

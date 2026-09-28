# Universal Capability-Aware Clock Design

**Status:** Proposed design for review
**Approved direction:** Jim Gatwood
**Date:** 2026-09-28
**Target:** All released CYM display boards

## 1. Purpose

Replace the WS-C5-28-only NTP Clock entry point with a universal `Clock` feature that works honestly on boards with different timing hardware. Every board gets the same clock experience, source arbitration, reliability vocabulary, and network-mode choices. Board capability definitions determine which sources are available and how uncertainty grows.

The feature must never imply that a board has an RTC or GPS when it does not. It must distinguish measured time from untrusted wall-clock contents and label uncharacterized reliability values as conservative estimates.

## 2. Release scope

The initial implementation covers all four released CYM targets:

- Waveshare WS-C5-28 (ESP32-C5, PCF85063A RTC, GPS UART)
- NM-CYD-C5 (ESP32-C5, no onboard RTC, GPS UART capability)
- CYD-2432S028 (ESP32, no onboard RTC, no enabled GPS UART)
- Hosyond ES3C35P 3.5 (ESP32-S3, no onboard RTC, GPS UART capability)

Classic and Modern remain separate navigation contracts over the same Clock screen. All four release targets must build and package before the cycle is pushed.

## 3. User-facing entry contract

A universal `Clock` tile appears in both navigation layouts:

- Classic: direct `Clock` tile on Home
- Modern: `Tools & System -> Clock`

Opening Clock always presents four choices. No choice is persisted as an automatic default.

1. `Display Only`
2. `Client NTP`
3. `AP NTP`
4. `Cancel`

`Cancel` closes the chooser without changing Wi-Fi, source state, or navigation.

### 3.1 Display Only

Display Only is strictly offline:

- it never starts Wi-Fi;
- it never joins a saved network;
- it never creates an AP;
- it never contacts a public NTP pool; and
- it never starts the UDP NTP responder.

It displays the best already-accepted source. GPS processing may continue on boards whose normal board-wide GPS task is active, because that does not violate the no-Wi-Fi contract. If neither GPS, RTC, nor a prior in-boot network discipline is trustworthy, Display Only shows `UNSYNCED` rather than presenting an arbitrary RTOS wall clock as valid.

### 3.2 Client NTP

Client NTP explicitly permits station Wi-Fi use. It reuses the existing credential workflow when no valid DHCP connection exists.

After DHCP:

- start the local UDP/123 responder;
- retain qualified GPS as the highest-priority source;
- when GPS is not qualified, make one bounded public-pool attempt;
- cap the public-pool wait at approximately five seconds;
- update the RTOS/POSIX system clock on every board after a valid response;
- repair the hardware RTC only when one exists and is unavailable, untrusted, or at least five seconds different; and
- continue local NTP service from the best trusted source if DNS or the pool is unavailable.

A successful public sync is a secondary source. A later qualified GPS lock supersedes it.

### 3.3 AP NTP

AP NTP creates a WPA2-protected local network and requires no upstream Internet connection. The dashboard displays the AP SSID, password, and server address.

The responder serves the best trusted GPS, RTC, public-NTP-disciplined RTOS, or RTOS-holdover time. If no trusted source exists, the responder remains diagnostic only and returns the NTP unsynchronized alarm state (leap indicator 3, stratum 16).

## 4. Shared timekeeper architecture

The existing `cym_timekeeper` becomes a capability-aware component available to every released SoC target. It remains independent of LVGL and network lifecycle.

Responsibilities:

- own UTC source selection and trust state;
- initialize system UTC from a trusted RTC when available;
- consume qualified GPS UTC observations when a board has GPS;
- consume validated public-NTP UTC observations after explicit Client NTP selection;
- maintain the RTOS clock when no RTC exists;
- write an available RTC only under bounded repair/discipline rules;
- expose immutable snapshots to the Clock UI and NTP responder;
- calculate source age and conservative uncertainty; and
- derive a user-facing reliability level without claiming measured accuracy.

The component must initialize safely with a null RTC bus. RTC code remains compiled behind board capability definitions and must not probe nonexistent hardware.

## 5. Board timing capability profile

Timing behavior belongs in board capability definitions rather than scattered conditions in UI code. Each board profile exposes:

- `has_rtc`
- `rtc_kind` and address when present
- `has_gps_uart`
- conservative RTC holdover drift in ppm
- conservative RTOS holdover drift in ppm
- base GPS UART uncertainty
- base public-NTP uncertainty
- a label identifying estimates as characterized or uncharacterized

Initial conservative, uncharacterized estimates:

| Board | RTC | GPS UART | RTC drift estimate | RTOS drift estimate | GPS base uncertainty | Public NTP base uncertainty |
|---|---|---|---:|---:|---:|---:|
| WS-C5-28 | PCF85063A | Yes | 50 ppm | 100 ppm | 500 ms | 250 ms |
| NM-CYD-C5 | None | Yes | N/A | 100 ppm | 500 ms | 250 ms |
| CYD-2432S028 | None | No | N/A | 150 ppm | N/A | 250 ms |
| Hosyond ES3C35P | None | Yes | N/A | 100 ppm | 500 ms | 250 ms |

These are engineering safety estimates, not hardware measurements. A later qualification cycle may replace a board's estimate without changing timekeeper consumers.

## 6. Source state model

The shared source model is:

- `UNSYNCED`
- `GPS_ACQUIRING`
- `GPS_LOCKED`
- `NETWORK_SYNC`
- `RTC_HOLDOVER`
- `RTOS_HOLDOVER`

Source priority and transition rules:

1. A qualified GPS lock is authoritative.
2. Explicit Client NTP may discipline the system clock when GPS is not locked.
3. A trusted RTC restores system UTC at boot and provides holdover after GPS or network loss.
4. Without an RTC, the RTOS clock becomes holdover after an accepted GPS or public-NTP discipline during the current boot.
5. A structurally plausible RTOS date alone is never proof of trust.
6. Rebooting a board without an RTC loses in-boot holdover trust until GPS or public NTP disciplines it again.
7. Display UTC offset remains presentation-only and never changes RTC, system UTC, or served NTP timestamps.

## 7. Reliability model

Every valid snapshot publishes:

- source identity;
- source age;
- estimated uncertainty in microseconds;
- reliability level;
- RTC availability and validity;
- GPS presence and qualification state; and
- whether the estimate is physically characterized.

Reliability levels:

### Excellent

Qualified GPS is active, a valid RTC exists, and estimated uncertainty is no greater than one second. This indicates both active discipline and durable holdover hardware; it does not claim PPS-level accuracy.

### Good

Qualified GPS without an RTC, or a recent validated public-NTP discipline, with estimated uncertainty no greater than two seconds.

### Holdover

A trusted RTC is carrying time after loss of active GPS or network discipline. Uncertainty grows from the last accepted discipline using the board's RTC drift estimate.

### Degraded

The RTOS clock is carrying time after loss of GPS or public NTP, or any otherwise-valid source has exceeded the better reliability thresholds. Uncertainty grows using the board's RTOS drift estimate.

### Untrusted

No accepted source exists in the current trust chain, the RTC reports invalid/oscillator-stop state, the epoch is outside the plausible range, or the timekeeper cannot produce a valid snapshot.

Reliability is dynamic. It must degrade as uncertainty grows rather than remaining fixed merely because the original source was good.

## 8. Clock dashboard

The shared Clock dashboard shows:

- large local display time and date;
- display UTC offset;
- active source badge;
- reliability level;
- estimated uncertainty;
- source age;
- RTC state (`valid`, `invalid`, or `not fitted`);
- GPS state (`locked`, `acquiring`, `not detected`, or `not supported`);
- current mode (`Display Only`, `Client NTP`, or `AP NTP`);
- network details only in Client/AP modes; and
- an explicit Exit control.

Examples:

- `Excellent | GPS disciplined + RTC | estimated ±500 ms`
- `Good | Public NTP / RTOS | estimated ±250 ms`
- `Holdover | RTC | estimated ±1.4 s`
- `Degraded | RTOS holdover | estimated ±3.2 s`
- `Untrusted | no synchronized source`

Where estimates are not physically characterized, the dashboard includes `estimated (unqualified)` in a compact status or details line.

The existing Clock brightness and display-offset settings become available on all released boards. Boards without an RTC show `RTC: not fitted` instead of hiding or disabling the Clock feature.

## 9. Network and teardown rules

Clock remains an exclusive tool while active.

- Display Only acquires no network ownership.
- Client NTP owns station Wi-Fi until Exit.
- AP NTP owns AP Wi-Fi until Exit.
- UDP/123 and mDNS run only in Client/AP modes.
- Exit performs ordered, bounded, idempotent teardown and restores the previous brightness and navigation destination.
- Entering Display Only after a network mode must not inherit a stale NTP server, mDNS registration, station connection, or AP.
- Opening Clock never silently starts Client or AP networking.

## 10. NTP quality mapping

- `GPS_LOCKED`: leap 0, stratum 1, reference ID `GPS`.
- `NETWORK_SYNC`: leap 0, stratum 2, network reference identity.
- `RTC_HOLDOVER`: leap 0 with existing RTC holdover quality behavior and increasing root dispersion.
- `RTOS_HOLDOVER`: leap 0 while the trust chain remains valid, with increasing root dispersion derived from board RTOS drift.
- `UNSYNCED` or untrusted time: leap 3, stratum 16.

Reliability labels are UI semantics; NTP protocol fields continue to follow source state and calculated uncertainty rather than copying the label directly.

## 11. Error handling

- Missing RTC is a capability state, not an error.
- Missing GPS is a capability or detection state, not a blocker for Clock entry.
- Public-pool DNS or timeout is nonfatal and bounded.
- Invalid public-NTP epochs are rejected.
- Network time never displaces an active qualified GPS lock.
- Failed RTC reads/writes do not invalidate a still-trusted active GPS or network source.
- Task creation, network initialization, mDNS, and UDP bind failures are displayed without freezing the dashboard.
- Display Only must remain usable even when all optional hardware and networking are unavailable.

## 12. Persistence

Persist only settings and hardware-backed trust that can survive reboot honestly:

- display UTC offset;
- Clock brightness;
- RTC trust metadata on RTC-equipped boards; and
- bounded discipline metadata needed to interpret RTC holdover.

Do not persist RTOS-only holdover trust across reboot on boards without an RTC. Do not persist a default Clock network mode.

## 13. Navigation and board isolation

The shared feature is compiled for every released full-CYM board, but hardware access remains capability-gated:

- WS-C5-28 retains PCF85063A access.
- GPS UART is used only on boards whose pin map declares it available.
- CYD-2432S028 does not open a nonexistent GPS UART.
- No board inherits another board's RTC address, GPIOs, or drift profile.
- Classic and Modern are each checked explicitly for tile placement and return behavior.

The Hosyond ES3C35P continues using its board-specific display/touch transport while consuming the shared Clock and timekeeper logic.

## 14. Verification contract

Automated source and behavior contracts must verify:

- universal Clock navigation in Classic and Modern layouts;
- the four-option chooser and no persisted default;
- Display Only performs no Wi-Fi, AP, mDNS, SNTP, or UDP-server startup;
- Client NTP performs bounded public synchronization and updates RTOS UTC on RTC-less boards;
- AP NTP works without public Internet;
- RTC probing/writes remain WS-C5-28 capability-gated;
- GPS initialization remains board-pin-map-gated;
- source transitions include RTOS holdover;
- uncertainty grows monotonically using the selected board profile;
- reliability levels degrade at defined boundaries;
- invalid/untrusted time cannot be reported as reliable;
- display offset never affects source UTC or NTP output;
- all settings and manifests use one cycle version; and
- all four released board images contain that version independently.

Build verification covers compilation and packaging only. Physical qualification remains required for actual GPS acquisition, RTC retention, oscillator drift, public-NTP behavior, AP interoperability, and long-duration holdover.

## 15. Acceptance criteria

The design is complete when:

1. Every released board exposes the same Clock entry and four choices.
2. Display Only never changes network state.
3. Every board can show trusted GPS, public-NTP, RTC, or RTOS-holdover time according to its actual capabilities.
4. Public NTP updates the RTOS system clock on boards without an RTC.
5. The WS-C5-28 RTC remains repaired and disciplined under the existing bounded policy.
6. The dashboard reports source, reliability, source age, and conservative estimated uncertainty.
7. Board-specific estimates live in capability definitions and are labeled unqualified until measured.
8. Missing hardware results in honest status, not feature removal or false confidence.
9. Focused contracts and the complete Python suite pass.
10. All four release targets build, package, and contain the shared release version.
11. Firmware delivery includes the WS-C5-28 raw full-image URL, SHA-256, size, and flash offset `0x0000`, plus hashes for the other release images.

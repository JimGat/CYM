# WS-C5-28 GPS-Disciplined NTP Clock Design

**Status:** Approved design
**Approved by:** Jim Gatwood
**Date:** 2026-09-27
**Target:** Waveshare ESP32-C5-Touch-LCD-2.8 (`ws-c5-28`)
**Release scope:** Design only; implementation and physical qualification require a separate plan and development cycle.

## 1. Purpose

Add a functional always-visible clock mode to the WS-C5-28 that:

- keeps the ESP32 system clock and the board's PCF85063A RTC synchronized from GPS;
- connects to a saved Wi-Fi network as a station and obtains its IPv4 address through DHCP;
- serves UTC to LAN clients through NTP on UDP port 123;
- displays the current clock, DHCP address, hostname, synchronization source, source age, estimated uncertainty, and request activity;
- continues serving from RTC holdover after loss of GPS;
- supports the existing GPS UART connection without requiring extra wiring; and
- preserves an interface for an optional PPS input in a later, separately qualified phase.

The mode is an appliance-style exclusive tool. While active, it owns Wi-Fi until the user exits. It is not a background service that must survive entry into other CYM radio tools.

## 2. Fixed product decisions

1. Scope is WS-C5-28 only. Existing behavior on NM-CYD-C5, CYD-2432S028, and Hosyond ES3C35P must remain unchanged.
2. GPS-to-system-clock-to-RTC synchronization is board-wide, not limited to the NTP Clock screen.
3. GPS, ESP32 system time, RTC, and NTP all use UTC.
4. The user-selected offset changes only the displayed clock.
5. NTP Clock mode is exclusive and serves until the user chooses Exit.
6. GPS loss transitions to RTC holdover; serving continues with clearly increasing uncertainty.
7. UART-only GPS is supported in version one. PPS is optional future work and is not required for the first release.
8. Wi-Fi uses DHCP, displays the assigned IPv4 address, advertises `cym-ntp.local`, and documents a router DHCP reservation as the preferred stable-address method.
9. The clock does not automatically dim. It remains at the saved NTP Clock brightness until Exit.
10. Persistent offset and brightness configuration lives under a board-gated `Settings -> Clock` tile.
11. Classic and Modern are separate navigation contracts that launch shared feature screens.
12. No accuracy figure is claimed until UART-only behavior has been physically measured.

## 3. Existing foundation

The WS-C5-28 board definition already identifies the PCF85063A RTC capability and board-specific GPS UART. The current GPS parser accepts valid RMC date/time and can initialize the ESP32 system clock, but it performs an initial synchronization rather than continuous discipline. CYM also already has saved Wi-Fi-client credentials, station connection, DHCP acquisition, and status-screen patterns that this feature can reuse.

Waveshare's board resources identify the PCF85063 RTC and the board's expansion interfaces.[2] The PCF85063A supports battery-backed calendar time, an oscillator-stop flag, a programmable offset register, and clock output functions that can support later calibration work.[1]

## 4. Architecture

### 4.1 `ws_c5_28_rtc`

A small WS-C5-28 hardware component owns PCF85063A register access.

Responsibilities:

- initialize the RTC on the board's existing I2C bus;
- read and write UTC calendar values;
- encode and decode packed BCD fields;
- validate seconds, minutes, hours, weekday, date, month, year, and leap-year combinations;
- expose oscillator-stop and validity state;
- expose offset-register read/write operations for later measured calibration; and
- serialize I2C access through the existing bus-ownership pattern.

It has no LVGL, GPS, Wi-Fi, or NTP dependency.

### 4.2 `cym_timekeeper`

A shared board-time service owns source selection and UTC discipline.

Responsibilities:

- initialize the ESP32 system clock from a trusted RTC at boot;
- consume validated GPS RMC UTC samples from the existing GPS pipeline;
- qualify GPS samples before accepting them as authoritative;
- step an invalid or grossly incorrect clock during initial acquisition;
- slew small corrections after synchronization to avoid backward wall-clock jumps;
- write stable GPS-disciplined UTC to the RTC at a bounded interval;
- maintain source state, source age, last discipline time, correction history, and uncertainty;
- persist a bounded RTC trust marker and last GPS-discipline epoch so an RTC value after reboot is not trusted merely because its calendar fields are plausible; and
- publish immutable snapshots for the UI and NTP server.

ESP-IDF provides wall-clock APIs and smooth adjustment support; this design keeps those APIs separate from monotonic timers used for task scheduling.[3]

Required snapshot interface:

```c
typedef enum {
    CYM_TIME_UNSYNCED = 0,
    CYM_TIME_GPS_ACQUIRING,
    CYM_TIME_GPS_LOCKED,
    CYM_TIME_RTC_HOLDOVER,
} cym_time_source_t;

typedef struct {
    struct timeval utc;
    cym_time_source_t source;
    bool valid;
    bool rtc_valid;
    bool gps_present;
    bool gps_fix;
    bool pps_active;
    uint64_t source_age_ms;
    uint64_t last_gps_sync_epoch;
    uint32_t uncertainty_us;
    int32_t last_correction_us;
} cym_time_snapshot_t;

bool cym_timekeeper_snapshot(cym_time_snapshot_t *out);
```

The implementation uses this ownership boundary and immutable-snapshot behavior.

### 4.3 `cym_ntp_server`

A transport component owns NTP protocol processing.

Responsibilities:

- bind UDP port 123 while NTP Clock mode is active;
- validate request length, version, and mode;
- read one immutable timekeeper snapshot per response;
- echo the client's transmit timestamp as the originate timestamp;
- populate reference, receive, and transmit timestamps;
- encode leap indicator, stratum, precision, root delay, root dispersion, and reference ID consistently with source state;
- rate-limit abusive request traffic;
- maintain request, malformed, rate-limited, and send-failure counters; and
- stop synchronously and release its socket during screen teardown.

NTP timestamp and quality-field behavior follows RFC 5905.[4]

It has no LVGL dependency and does not own GPS, RTC, mDNS, or Wi-Fi lifecycle.

### 4.4 `ntp_clock_screen`

The feature screen owns operating-mode lifecycle and presentation.

Responsibilities:

- acquire exclusive Wi-Fi ownership;
- connect with the existing saved station credentials;
- wait a bounded time for DHCP;
- start mDNS and advertise `cym-ntp.local` plus `_ntp._udp`;
- start the NTP responder only after a usable network interface exists;
- render the dashboard from timekeeper, network, and NTP snapshots;
- keep the configured brightness unchanged while active;
- offer bounded Retry after network failure; and
- perform ordered, idempotent teardown on Exit, Back, Home, or screen deletion.

### 4.5 `clock_settings_screen`

A board-gated `Settings -> Clock` screen owns persistent presentation settings and time diagnostics.

Version-one controls:

- display UTC offset;
- NTP Clock brightness; and
- Save/Cancel behavior consistent with other CYM settings.

Read-only status:

- RTC valid/invalid and oscillator-stop state;
- current UTC source;
- last successful GPS-to-RTC update; and
- last known holdover age.

Future PPS settings belong on this page:

- PPS enabled/disabled;
- board-specific PPS GPIO;
- active edge; and
- detected-pulse state.

Version one does not expose nonfunctional PPS controls. It only reserves a settings schema and UI boundary that can be extended later.

## 5. Time-source state machine

### 5.1 `UNSYNCED`

Entry conditions:

- no qualified GPS UTC;
- RTC oscillator-stop or invalid calendar state;
- RTC lacks the persisted trust marker from a prior accepted GPS discipline; or
- uncertainty exceeds the implementation's representable/trustworthy limit.

Behavior:

- dashboard shows `UNSYNCED`;
- wall clock is not presented as authoritative;
- NTP replies use leap indicator 3 and stratum 16; and
- server remains available for diagnostics but clients can reject its time.

### 5.2 `GPS_ACQUIRING`

Entry conditions:

- GPS UART traffic is present but consecutive valid RMC samples have not yet passed qualification.

Behavior:

- continue trusted RTC holdover when available;
- otherwise remain unsynchronized;
- reject checksum failures, invalid dates, discontinuous samples, and missing-validity samples; and
- display acquisition state without claiming a GPS lock.

### 5.3 `GPS_LOCKED`

Entry conditions:

- multiple consecutive valid and internally consistent RMC UTC samples;
- acceptable relationship between reported UTC and monotonic arrival timing; and
- no rejected discontinuity.

Behavior:

- GPS is the authoritative UTC source;
- initial gross error may be stepped;
- subsequent small corrections are slewed;
- RTC is updated after stable acquisition and then no more often than every 10 minutes;
- trust metadata is persisted on source transition and at a wear-conscious interval, not for every GPS sentence;
- NTP identifies a primary GPS reference; and
- uncertainty includes UART transport latency, sentence-arrival jitter, scheduling delay, and observed correction residuals. Before physical characterization, GPS-locked UART uncertainty starts conservatively at 500 ms and is shown as uncalibrated. RTC holdover uncertainty grows from that value at 50 ppm until board measurements justify a more conservative calibrated model.

### 5.4 `RTC_HOLDOVER`

Entry conditions:

- previously trusted GPS time exists;
- GPS qualification is lost; and
- RTC remains valid without oscillator-stop indication.

Behavior:

- continue UTC from the system clock and RTC-backed trust chain;
- display holdover age from the last accepted GPS discipline;
- increase uncertainty monotonically based on measured or conservatively bounded drift;
- continue NTP service while reporting increased root dispersion; and
- return to `GPS_LOCKED` only after reacquisition qualification succeeds.

NTP stratum is not used as a substitute for an accuracy estimate. Trusted RTC holdover uses leap indicator 0, stratum 1, reference ID `RTC`, and monotonically increasing root dispersion. Source quality is also shown through source age and the on-screen uncertainty. Untrusted time uses leap indicator 3 and stratum 16.

## 6. Clock discipline rules

1. Use monotonic time for intervals, timeouts, holdover duration, and scheduler decisions.
2. Use wall-clock UTC only for calendar display, RTC writes, and NTP timestamps.
3. A valid trusted RTC may step an invalid ESP32 wall clock at boot.
4. Initial GPS acquisition may step a grossly wrong wall clock.
5. Once synchronized, small corrections slew; repeated backward steps are prohibited.
6. GPS RMC is second-resolution data delivered over UART. Version one timestamps sentence completion with monotonic time and uses a board-measured constant-latency correction only if physical testing validates it. Otherwise the correction remains zero and the uncertainty envelope includes transport delay.
7. RTC updates require stable GPS lock and are rate bounded. PCF register writes are not performed for every RMC sentence.
8. Display offset never modifies source UTC.
9. RTC offset-register calibration is not automatic in version one. Any later calibration feature requires measured drift, bounds checking, and separate hardware qualification.
10. Optional PPS discipline is deferred. The timekeeper interface carries `pps_active` so PPS can later improve phase alignment without changing consumers.

## 7. NTP response contract

For a valid client request:

- response mode is server;
- version is compatible with the request within the supported range;
- originate timestamp exactly echoes the client transmit timestamp;
- receive timestamp is captured as early as practical after socket receipt;
- transmit timestamp is captured immediately before send;
- reference timestamp identifies the last accepted discipline event;
- all timestamps use UTC NTP fixed-point format;
- packet fields are written in network byte order; and
- malformed or unsupported requests are dropped and counted without affecting the timekeeper.

Source-state mapping:

| State | Leap indicator | Stratum | Reference ID | Dispersion |
|---|---:|---:|---|---|
| GPS locked | synchronized | 1 | `GPS` | UART-derived measured/conservative uncertainty |
| RTC holdover | synchronized while trusted | 1 | `RTC` | increases with holdover age |
| Unsynchronized | 3 | 16 | `INIT` | unsynchronized maximum/conservative value |

RTC holdover remains stratum 1 because the server is still directly traceable to its last GPS discipline event; stratum describes hierarchy rather than accuracy. `RTC` and monotonically increasing root dispersion distinguish holdover from active GPS lock. When the timekeeper no longer trusts the holdover value, replies switch to leap indicator 3 and stratum 16 while continuing to answer diagnostically.

A global token bucket protects the device from UDP floods: refill 8 requests per second with a burst capacity of 32. A per-source bucket refills at 2 requests per second with a burst capacity of 4. Excess requests are dropped and counted. These values leave ample capacity for normal LAN polling while bounding CPU and socket work.

## 8. Wi-Fi and discovery lifecycle

Startup order:

1. Enter NTP Clock screen.
2. Apply saved NTP Clock brightness.
3. Acquire exclusive Wi-Fi ownership.
4. Load existing saved Wi-Fi Client credentials.
5. Connect as a station with bounded timeout/retry.
6. Wait for DHCP IPv4 assignment.
7. Display the assigned DHCP address.
8. Start mDNS as `cym-ntp.local` and advertise `_ntp._udp`.
9. Bind UDP/123 and display `SERVING` only after bind succeeds.

If no credentials exist, the screen directs the user to:

`Settings -> Data Transfer -> WiFi Client`

If mDNS fails but UDP bind succeeds, IP-based NTP remains operational and the dashboard shows mDNS failure separately. If DHCP or UDP bind fails, the clock remains usable and the dashboard shows `NTP OFFLINE` with Retry and Exit.

Teardown order:

1. Mark the screen as stopping and reject new UI work.
2. Stop accepting NTP requests and close UDP/123.
3. Stop mDNS advertisement.
4. Delete screen-owned LVGL timers and callbacks.
5. Release or disconnect Wi-Fi through the existing bounded ownership path.
6. Clear feature state and return through the correct navigation contract.

Teardown must be idempotent and safe from Exit, Back, Home, and LVGL delete callbacks.

## 9. Dashboard design

The selected design is the operational dashboard for the native 240 x 320 portrait display.

Required visible fields:

- header: `NTP CLOCK`;
- source badge: `GPS LOCK`, `GPS ACQUIRING`, `RTC HOLDOVER`, or `UNSYNCED`;
- large 24-hour `HH:MM:SS` time;
- date;
- `DISPLAY UTC[+/-]HH:MM - NTP UTC`;
- `DHCP IP: a.b.c.d` or an explicit offline state;
- `Hostname: cym-ntp.local` or an explicit mDNS-failure state;
- `NTP: UDP/123 SERVING` or exact offline reason;
- GPS age or RTC holdover age;
- method: `UART` in version one and `PPS` only when later qualified;
- estimated uncertainty;
- successful NTP request count; and
- one clear `Exit NTP Clock` control.

The screen updates time and status at 1 Hz without rebuilding the LVGL object tree. NTP, GPS, and RTC tasks never directly mutate LVGL objects.

Brightness behavior:

- default NTP Clock brightness is 100 percent;
- user-selected brightness is stored separately from general CYM brightness;
- there is no automatic dimming, timeout, or Go Dark transition in this mode; and
- the previous general brightness is restored on Exit.

## 10. Clock Settings design

`Settings -> Clock` is visible only when the board configuration enables this WS-C5-28 clock feature.

### Display offset

- range: UTC-12:00 through UTC+14:00;
- step: 15 minutes;
- default: UTC+00:00;
- no automatic daylight-saving rules in version one; and
- affects display only.

### NTP Clock brightness

- default: 100 percent;
- manually selectable within the board's safe backlight range;
- persists in NVS; and
- remains constant for the duration of NTP Clock mode.

### Persistence

Clock settings use a versioned settings structure or individually version-safe NVS keys. Invalid, missing, or out-of-range values fall back to defaults. Save is explicit and reports failure; Cancel leaves persisted settings unchanged.

## 11. Navigation

The shared feature screens have separate navigation entries and return contracts.

Classic:

- `WiFi -> NTP Clock` launches the operating mode.
- `Settings -> Clock` opens persistent clock configuration.

Modern:

- the Wi-Fi category contains `NTP Clock` and launches the same operating mode;
- the Settings path contains `Clock` and launches the same settings screen; and
- Back returns to the correct Modern category rather than assuming Classic tile ancestry.

Both paths are board-gated for WS-C5-28. GPS Info remains a diagnostic screen and does not absorb NTP Clock operation or persistent Clock settings.

## 12. Failure handling

| Failure | Required behavior |
|---|---|
| RTC invalid or oscillator stopped | Reject RTC as authoritative; show `RTC INVALID`; wait for qualified GPS |
| RTC calendar plausible but never GPS-trusted | Remain unsynchronized; do not trust factory/stale time |
| GPS UART absent | Use trusted RTC holdover if available; otherwise unsynchronized |
| GPS data present but invalid | Show acquiring/error state; reject sample; retain prior trusted source |
| GPS lost after lock | Enter RTC holdover and grow uncertainty |
| Large GPS discontinuity after lock | Reject pending sample set, remain on prior trusted source, log reason |
| No saved Wi-Fi credentials | Keep clock running; direct user to WiFi Client settings |
| Association or DHCP timeout | Show `NTP OFFLINE`; offer bounded Retry and Exit |
| mDNS failure | Keep IP-based NTP active; show hostname unavailable |
| UDP/123 bind failure | Do not show `SERVING`; close partial resources; offer Retry and Exit |
| Allocation/task failure | Fail closed, clean up partial state, show actionable error |
| NTP flood/malformed packet | Drop/rate-limit and count; do not block GPS, RTC, or UI work |
| Exit during startup | Cancel bounded startup and run the same idempotent teardown |

## 13. Security and operational boundaries

- The feature is a LAN UDP service and provides no NTP authentication in version one.
- It binds only while the user has explicitly entered NTP Clock mode.
- It does not open an access point, captive portal, or Internet-facing service.
- It does not alter saved Wi-Fi credentials.
- Packet parsing accepts only the minimum request fields needed for an NTP server response and validates lengths before access.
- Request processing uses fixed-size buffers and bounded work.
- Logs never print Wi-Fi passwords or secret material.

## 14. Automated verification

Host/unit tests:

- RTC BCD encode/decode;
- valid and invalid calendar combinations, including leap years;
- oscillator-stop and trust-marker decisions;
- GPS qualification and discontinuity rejection;
- boot, acquisition, lock, loss, holdover, reacquisition, and unsynchronized transitions;
- wall-clock step-versus-slew decisions;
- holdover-age and uncertainty growth;
- NTP epoch/fraction conversion and network byte order;
- known NTP packet vectors;
- originate, receive, reference, and transmit timestamp placement;
- leap/stratum/reference/dispersion mapping for every state;
- malformed packet handling and rate limiting;
- NVS defaults, range validation, save/cancel, and migration;
- Classic and Modern navigation/Back contracts; and
- compile-time board gating.

Build gate:

- build every currently released CYM board before a cycle push;
- run the full Python contract suite; and
- verify unsupported board packages and manifests remain unchanged except for the shared version cycle when release work is authorized.

## 15. Physical WS-C5-28 qualification

Required before claiming hardware support:

1. Verify PCF85063A address, register behavior, oscillator-stop handling, and UTC read/write.
2. Verify battery-backed RTC retention across USB power removal.
3. Prove boot from a previously GPS-trusted RTC without GPS present.
4. Prove an untrusted plausible RTC value is not accepted as authoritative.
5. Verify consecutive valid GPS RMC samples acquire lock and discipline system UTC.
6. Verify stable GPS updates the RTC and persisted trust metadata at bounded intervals.
7. Disconnect GPS and verify transition to RTC holdover without stopping NTP.
8. Reconnect GPS and verify qualified reacquisition without backward time jumps.
9. Confirm actual DHCP IPv4 address and `cym-ntp.local` on screen.
10. Query UDP/123 from independent Linux and Windows clients.
11. Capture responses and verify all NTP timestamps and quality fields.
12. Measure UART-only offset and jitter against an independent trusted reference.
13. Report median, 95th-percentile, and maximum error with test conditions.
14. Confirm the displayed and advertised uncertainty conservatively contains observed error.
15. Exercise malformed requests and bounded high-rate traffic without starving GPS or UI tasks.
16. Run repeated enter/exit cycles and check tasks, sockets, timers, callbacks, heap, and Wi-Fi ownership.
17. Run an extended illuminated-screen and NTP-request soak.
18. Confirm no automatic dimming and persistent Clock Settings brightness.

Compilation alone is not hardware qualification. The release notes must describe UART-only timing honestly and must not imply PPS accuracy.

## 16. Deferred PPS enhancement

PPS is a later phase, not version-one scope.

The future design may:

- allow an approved free GPIO to be selected under `Settings -> Clock`;
- timestamp the configured edge in an ISR using a monotonic hardware timer;
- correlate PPS edges with qualified NMEA UTC;
- estimate oscillator frequency error and phase residual;
- tighten the timekeeper uncertainty model; and
- label the dashboard method `PPS` only after edge detection and discipline are healthy.

GPIO selection must be WS-C5-28-specific and checked against GPS UART, display/touch, SD, RF-HAT, and other board resources. No PPS GPIO is assumed or reserved by this version-one design.

## 17. Acceptance criteria

The feature is complete only when:

- board-wide GPS -> system UTC -> RTC synchronization works on physical WS-C5-28 hardware;
- trusted RTC boot and RTC holdover work across a power cycle;
- the NTP Clock screen connects by DHCP and prominently displays the assigned IPv4 address;
- `cym-ntp.local` works when mDNS succeeds;
- independent clients receive valid NTP responses on UDP/123;
- NTP and RTC remain UTC while display offset affects only the screen;
- dashboard state, source age, and uncertainty match real source conditions;
- clock brightness remains fixed until Exit with no automatic dimming;
- Classic and Modern navigation and teardown pass independently;
- measured UART-only timing results are documented without overstating accuracy;
- all released board builds and contract tests pass; and
- Jim physically validates the WS-C5-28 behavior before release promotion.

## Sources

[1] https://www.nxp.com/docs/en/data-sheet/PCF85063A.pdf
[2] https://github.com/waveshareteam/ESP32-C5-Touch-LCD-2.8
[3] https://docs.espressif.com/projects/esp-idf/en/latest/esp32c5/api-reference/system/system_time.html
[4] https://www.rfc-editor.org/rfc/rfc5905.html

# WS-C5-28 GPS-Disciplined NTP Clock

The NTP Clock is available only in the Waveshare WS-C5-28 firmware target.
It uses the board RTC and UART GPS input to maintain UTC and serves that time
on the local network while the NTP Clock screen is open.

## Before use

1. Choose a network mode whenever NTP Clock opens. `Client Mode` joins an existing Wi-Fi network; `AP Mode` creates a local offline NTP network; `Cancel` leaves networking unchanged.
2. For Client Mode, have the target Wi-Fi SSID and password available. If CYM does not already have a usable DHCP connection, it presents the same Wi-Fi Client scan and credential prompt used by Data Transfer.
3. A GPS receiver is optional. When fitted, connect it to the WS-C5-28 UART connector. Version one uses UART RMC time only; PPS is not implemented or configurable.
4. For Client Mode clients that require a stable numeric address, create a DHCP reservation for the WS-C5-28 in the router.

## Clock settings

Open `Settings -> Clock`.

- `Display UTC Offset` changes only the time shown on the display. It accepts
  15-minute steps from UTC-12:00 through UTC+14:00.
- `NTP Clock Brightness` selects the brightness held continuously while the
  clock screen is active. The clock does not automatically dim.
- `Save Clock` stores both settings. `Cancel` restores the saved values.

The RTC, ESP32 system clock, GPS observations, and NTP replies always remain in
UTC. The display offset never changes RTC contents or NTP replies.

## Start and stop

- Classic layout: `Home -> NTP Clock`
- Modern layout: `Tools & System -> NTP Clock`

Opening NTP Clock always shows `NTP Network Mode`; no mode is saved as a default.

### Client Mode

If a valid DHCP address is not already available, the feature opens `WiFi for
NTP Clock`, reusing the Data Transfer Wi-Fi Client scan/manual credential flow.
After a successful connection and DHCP lease, it automatically continues into
the clock. The dashboard shows the actual IPv4 address prominently and starts
NTP on UDP port 123. It also advertises:

- hostname: `cym-ntp.local`
- service: `_ntp._udp`

Configure an NTP client with the displayed IPv4 address or, on networks where
mDNS is supported, `cym-ntp.local`.

When GPS is not locked, Client Mode checks the timekeeper and makes one bounded
public-pool request to `pool.ntp.org`. The wait is capped at approximately five
seconds. A valid response repairs system UTC and writes the PCF85063A RTC when
the existing source is unavailable, untrusted, or differs by at least five
seconds. If the RTC is already within five seconds, it is not rewritten. DNS or
pool failure leaves the RTC source in service and does not stop the local NTP
responder. A later qualified GPS lock supersedes public-NTP recovery.

### AP Mode

AP Mode requires no router or Internet service. It creates a WPA2-protected
`CYM-NTP-xxxxxx` network and shows its SSID, password, and AP address on the
dashboard. Join that network and configure clients to use the displayed AP
address (normally `192.168.4.1`) as their NTP server. AP Mode serves qualified
GPS time or trusted RTC holdover; it does not contact a public NTP pool.

`Cancel` closes the mode chooser without starting or changing Wi-Fi. NTP service
and its selected network mode remain active until `Exit NTP Clock` is selected.
Exit stops UDP/123, removes the mDNS advertisement, releases the selected network
mode, and restores normal display brightness and navigation.

## Status meanings

- `GPS LOCK`: qualified GPS RMC time is disciplining the system clock; NTP is
  served as stratum 1.
- `GPS ACQUIRING`: GPS data is present but still qualifying. A valid RTC-derived
  holdover remains authoritative if available.
- `RTC HOLDOVER`: GPS has been lost or is unavailable, but the clock continues
  serving from RTC-backed UTC. The screen shows holdover age and increasing
  uncertainty.
- `PUBLIC NTP`: Client Mode recovered or verified UTC from the public pool and
  repaired the RTC when needed. It remains secondary; GPS can supersede it.
- `UNSYNCED`: no trustworthy GPS or RTC time is available. NTP replies report
  the unsynchronized alarm state and stratum 16; clients should reject them.

UART-only GPS timing has greater uncertainty than PPS-disciplined timing. PPS is
a future enhancement and is intentionally absent from the current settings.

## Troubleshooting

- No DHCP address: use the `WiFi for NTP Clock` prompt to scan or enter credentials. `Retry WiFi` returns to that prompt after a dashboard connection failure.
- `cym-ntp.local` does not resolve: use the displayed IPv4 address and verify
  that the client network permits mDNS multicast.
- UDP/123 is unreachable: confirm the screen says `NTP: UDP/123 SERVING` and
  check local firewall or client VLAN rules.
- Time display differs from NTP: this is expected when a display UTC offset is
  configured; NTP remains UTC.
- Public NTP unavailable: local serving starts before recovery is attempted and continues from a trusted RTC. Verify DNS/Internet access if RTC repair is needed.
- AP clients cannot reach NTP: join the displayed `CYM-NTP-xxxxxx` SSID and use the displayed AP IP directly; Internet access is not expected in AP Mode.
- Persistent `UNSYNCED`: use Client Mode once to recover from the public pool, or verify GPS UART wiring and reception, then check RTC status under `Settings -> Clock`.

Compilation validates the firmware integration but does not prove RTC
retention, GPS timing accuracy, mDNS behavior, network reachability, or long
soak stability on physical hardware.

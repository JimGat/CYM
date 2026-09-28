# WS-C5-28 GPS-Disciplined NTP Clock

The NTP Clock is available only in the Waveshare WS-C5-28 firmware target.
It uses the board RTC and UART GPS input to maintain UTC and serves that time
on the local network while the NTP Clock screen is open.

## Before use

1. Save the Wi-Fi client SSID and password in CYM Wi-Fi settings.
2. Connect a supported GPS receiver to the WS-C5-28 UART connector. Version one
   uses UART RMC time only; PPS is not implemented or configurable.
3. For clients that require a stable numeric address, create a DHCP reservation
   for the WS-C5-28 in the router. The firmware itself remains a DHCP client.

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

- Classic layout: `WiFi -> NTP Clock`
- Modern layout: `Tools & System -> NTP Clock`

The screen connects with the saved Wi-Fi credentials, obtains an address by
DHCP, and starts the NTP service on UDP port 123. It shows the actual IPv4
address prominently. It also advertises:

- hostname: `cym-ntp.local`
- service: `_ntp._udp`

Configure an NTP client with the displayed IPv4 address or, on networks where
mDNS is supported, `cym-ntp.local`.

NTP service and its network ownership remain active until `Exit NTP Clock` is
selected. Exit stops UDP/123, removes the mDNS advertisement, and restores the
normal display brightness and navigation.

## Status meanings

- `GPS LOCK`: qualified GPS RMC time is disciplining the system clock; NTP is
  served as stratum 1.
- `GPS ACQUIRING`: GPS data is present but still qualifying. A valid RTC-derived
  holdover remains authoritative if available.
- `RTC HOLDOVER`: GPS has been lost or is unavailable, but the clock continues
  serving from RTC-backed UTC. The screen shows holdover age and increasing
  uncertainty.
- `UNSYNCED`: no trustworthy GPS or RTC time is available. NTP replies report
  the unsynchronized alarm state and stratum 16; clients should reject them.

UART-only GPS timing has greater uncertainty than PPS-disciplined timing. PPS is
a future enhancement and is intentionally absent from the current settings.

## Troubleshooting

- No DHCP address: verify saved Wi-Fi credentials and select `Retry WiFi`.
- `cym-ntp.local` does not resolve: use the displayed IPv4 address and verify
  that the client network permits mDNS multicast.
- UDP/123 is unreachable: confirm the screen says `NTP: UDP/123 SERVING` and
  check local firewall or client VLAN rules.
- Time display differs from NTP: this is expected when a display UTC offset is
  configured; NTP remains UTC.
- Persistent `UNSYNCED`: verify the GPS UART wiring and reception, then check
  RTC status under `Settings -> Clock`.

Compilation validates the firmware integration but does not prove RTC
retention, GPS timing accuracy, mDNS behavior, network reachability, or long
soak stability on physical hardware.

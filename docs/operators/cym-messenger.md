# CYM Messenger v3.0.47 development candidate

Development v3.0.47: all nine profiles built and 36 packaged artifacts verified.
Classic static-memory overflow was corrected without stack/display/feature
reductions. Paired-device physical acceptance remains NOT_RUN.
Board labels and Stable are unchanged.

## Intended two-device steps (NOT_RUN on hardware)

1. Both devices: Classic Home > Messenger; Modern Tools/System > Messenger.
   Own STA address appears after the off-UI identification job. A MAC identifies
   an interface, not a human.
2. ESP-NOW > Setup: on A enter B's STA MAC; on B enter A's STA MAC. Enter the same
   private LMK (exactly32hex digits) and channel on both. Default channel1;
   common2.4GHz channels1-11 intersect driver country limits. No5GHz/mesh/discovery.
3. Key starts masked; Reveal is explicit. New key generates off UI only when the
   existing WiFi power worker reports an active/applied policy (hardware entropy
   available). Otherwise setup/radio error appears. Stop before changing keys.
   Copy the key privately to the peer. No public default/broadcast key exchange.
4. Start on both within30seconds. Starting > Waiting for peer > Session ready.
   Start refuses active scan/AP/file transfer/Clock/BLE/other radio work instead
   of tearing it down. Current candidate requires an initialized, running idle
   WiFi STA driver, unassociated and not promiscuous. It does NOT start/replace
   a foreign mode. Stop other tools, return Home and retry; with no idle WiFi
   driver, Start cannot proceed. No silent plaintext fallback or channel takeover.
5. Tap composer: existing-style green CYM keyboard, with Send above it. Counter
   is UTF-8 BYTES, not glyphs. Max160bytes; overlong drafts stay editable, Send
   refuses them. NUL/controls, malformed UTF-8 and '#' recolor markup are refused.
   Valid Unicode does not imply the font renders every glyph.
6. Send: You row means queued locally, not Delivered. Pending application ACK >
   Delivered (not read) only after authenticated matching peer/session/message/
   content ACK. MAC success alone never delivers. Three attempts800ms apart,
   then Delivery unconfirmed (may have arrived). Offline/wrong key/channel can
   look identical; no false precise diagnosis. Latest outgoing delivery state
   only; four visible conversation rows total.
7. Stop, Back or Home requests off-UI cleanup. Radio destinations defer until
   ownership releases; normal input remains live. Cleanup uncertainty retains
   ownership and shows Stop-to-retry. Never force clear it. After either peer
   restarts/reboots, BOTH must Stop/Start together. Remote session is pinned;
   no automatic replacement, bridging or fallback.
8. Protocol toggle preserves the exact composer draft. BLE, LocalSend,
   LoRa/Reticulum and IR/CardputerZero are Not implemented and cannot send.
   IR requires supported profile plus configured NM-RF-HAT; configured is NOT
   physical detection. Separate IR-board config and CardputerZero framing are
   deferred. LoRa never implies Reticulum/LXMF interoperability.

## Storage/security boundary

Peer/key/channel are session-only, not saved to NVS; no fake saved state or
persistent message logs. No real keys/plaintext messages are serial-logged.
Setup text remains in LVGL until leaving the screen. Clearing buffers does not
promise forensic erasure from allocator/cache copies. No NVS-at-rest protection
is claimed. SDK encrypted unicast uses the shared128-bit LMK. The installed
receive callback has no trusted encryption flag; full HMAC-SHA256 additionally
binds domain, both STA MACs, header and body. Installed mbedTLS/PSA supplies HMAC,
not a custom cipher. Local random PMK wraps LMK locally; it need not match peer.
Fresh128-bit session challenges, pinned peer sessions and monotonic message IDs
reject stale DATA/ACK in this restart model; no forward-secrecy/human-identity or
independent security-audit claim. ACK only after validated bounded-inbox accept;
duplicate retransmissions ACK again without duplicate display, overflow no ACK.

## Evidence limits

Focused core scenarios and two semantic assertion-killed mutants passed. Complete
production worker executes against deterministic SDK/RTOS fault endpoints and an
OpenSSL-backed PSA shim, not target SDK timing. Full UI include runs actual LVGL
in24 layout/theme/geometry combinations (624checks), not full home navigation or
physical touch. Exact totals/logs/failures are in the remote evidence directory
/home/dev/projects/cym-messenger-047/parent-final-verification.json.

Physical gates NOT_RUN: paired encrypted send/receive, wrongkey/channel/offline,
ACK loss/reboot/replay, RF legality/range, repeated navigation against Clock/AP/
file transfer/scan/BLE/power, channel/band/power restoration, real keyboard
responsiveness and internal heap/largest/DMA/4096-stack minima on every MCU.

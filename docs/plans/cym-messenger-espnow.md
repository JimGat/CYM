# CYM Messenger ESP-NOW implementation plan

Goal: a direct, encrypted, single-peer Messenger with protocol-selecting existing-style UI, no logging or discovery. Implementation belongs to JimGat; no imported contribution is claimed.

Architecture: production portable codec/session in ESP32C5/main/cym_messenger_core.{c,h}; SDK worker in cym_messenger.{c,h}; thin cym_messenger_ui.inc in canonical main.c. Three main CMake consumers compile the same sources. No generic plugin system.

1. Write and run tests/run_messenger_core_host.py RED, then implement explicit byte codec, strict UTF-8 validator, authenticated session handshake and DATA/ACK state. Run native tests and deliberate behavioral mutations.
2. Test SDK worker allocation/unwind, receive copying, stop/reentry, installed SDK constants and owner boundaries before integration. Add B reservation owner 5 and narrow D lifecycle exclusion, never bypass existing radio_reset.
3. Test actual installed LVGL for Classic/Modern routes, portrait/landscape/theme geometries, shared keyboard style, byte count and drafts. Wire isolated UI after production core/adapter works.
4. Update existing backlog chat item, operator manual, staged Wiki/release notes, tests manifest/inventory. Bump all family versions/manifests/current contracts v3.0.46 -> v3.0.47 before target compilation.
5. Run focused, tracked-only portable export, maintained portable and SDK-native, broad and 40 standalone release gates. Freeze sources and run nine-board matrix with guarded actual Ninja -j2, <=2 concurrent. Verify 36 outputs, configurations, rollback preservation, memory maps and physical NOT_RUN gates.

Wire v1: bytes 0..1 CM; byte2 version1; byte3 type (HELLO1, CHALLENGE2, READY3, DATA4, ACK5); 4..19 random sender session; 20..35 recipient session; 36..39 big-endian uint32 id; 40..41 big-endian uint16 body length; body; 32-byte HMAC-SHA256. Max DATA =42+160+32=234 <=250. HMAC input is ASCII CYM-MSG-v1 followed by source STA MAC, destination STA MAC and header+body. Key is the user LMK, only encrypted unicast SDK peers. Full tag comparison is constant time. No structure serialization. ACK body is original DATA authentication tag, binding accepted bytes.

Fresh hardware random 128-bit sessions per Start. HELLO recipient zero, CHALLENGE echoes HELLO nonce as recipient; READY confirms both nonces. Pin first confirmed remote session for entire Start lifetime, reject other sessions. Both devices must Stop/Start after either reboots. No automatic session replacement. Old HELLO cannot replace established session. IDs start1, refuse uint32 exhaustion rather than wrapping. One in-flight DATA, four application inbox slots; newest id must increase. Duplicate last DATA tag repeats ACK but not display; no ACK on full inbox. ACK only after authenticated valid text enqueued. Three sends separated by 800ms, then Delivery unconfirmed; MAC completion never Delivered. Monotonic uint32 elapsed subtraction handles tick wrap.

SDK receive callback exposes no encryption flag (installed esp_now.h); HMAC closes source-MAC-only trust. SDK PMK encrypts local LMK storage, so per-device random PMK does not change shared over-air LMK. No default public keys, broadcasts, persistent settings or message logs. Session-only credentials, explicitly masked/reveal; randomness generated off UI. Country limits intersect 2.4GHz channels1..11 conservatively. No 5GHz or mode/channel takeover while utility owns radio.

Radio caller map: B wifi_attacks_radio_claim owners1 AP,2 Clock,3 file transfer,4 reset; extend only owner5 Messenger. main clock_radio_admit/ensure_wifi_mode/ensure_ble_mode/radio_reset are shared navigation boundaries; keep foreign operations refused during Messenger. D cym_wifi_init/start/stop/deinit serialize power lifecycle, Messenger reserves driver mutation lifetime after radio admission, restores original channel/band/power state before releasing. Background Clock/NTP/AP/file transfer, WiFi scanning/wardrive/OT survey and BLE are regression exposures; no feature teardown to force Start. Explicit Start shows busy if mode/controller is not safely idle.

Memory: no always-on session arrays; lazily allocate bounded internal context, four-slot callback ring and4096-byte internal worker stack. LVGL alone owns widgets; worker owns crypto, SDK and core. Callback only copies <=250 bytes to bounded RX queue without blocking; no callback-held pointers. Stop closes admission, unregisters receive, retires callback-visible pointer under the same copying lock and lets the worker self-delete before reclaiming its task stack, retaining owner on uncertain SDK release. UI stop never waits or performs networking. Draft retained during protocol toggles, not persistent logging. Static per-board baseline maps consulted including Classic v3.0.46 data27731/bss96824/IRAM105523; final ELF/config margins must be measured; runtime heap/largest/DMA/stack unknown without hardware.

Impact matrix: core isolated -> codec/auth/replay/native mutations; SDK -> allocation/init/register/send/stop/reentry/callback failures; B/D owner -> Clock/AP/file transfer/power lifecycle tests; main UI -> both layouts/themes/orientations and keyboard; CMake/version -> all nine builds and package checks. Preserve pins/display/SD/USB-GPS/configs/bootloader/partitions; no capability disabling, no shared keyboard refactor. IR only future NM-RF-HAT-supported configured profiles; configured is not physical detection. BLE/LocalSend/LoRa/Reticulum/IR are visibly unimplemented, independent framing adapters; no bridging or compatibility promises.

Physical gates NOT_RUN: paired encrypted messaging including wrongkey/channel/offline, RF legality/range, real keyboard responsiveness, heap/DMA largest-block/stack minima and repeated exit/reentry. Builds and host tests cannot qualify these. No flashing/publication/Stable promotion.

## Final software qualification

The initial Classic link overflow was corrected by eliminating a redundant 1028-byte static hex copy in saved GATT details. A bounded view uses the existing mutable JSON buffer and restores its original byte after rendering. No added allocation or stack/display/capability reduction. Configs, bootloaders and partitions preserved.

Maintained gates: 89 PASS, 369 unittest cases, 57 harness invocations (overlapping counts). Broad suite: 769 PASS plus one private-capture skip. All 40 release standalones passed. Messenger actual-LVGL: 624 checks; mocked worker: 319 checks. Saved GATT renderer: 5,505 sanitized parity/input-restoration cases.

First transport is direct encrypted ESP-NOW, single peer, 160 UTF-8 bytes; application ACK is not a read receipt. Setup/history are session-only. Existing idle WiFi STA is required; conflicting radio owners are refused. Future BLE, LocalSend, LoRa/Reticulum and NM-RF-HAT-only IR remain visibly unimplemented.

SDK retention after first use, callbacks under real concurrency, physical keyboard response and runtime heap/stack minima require target acceptance. No independent security audit is claimed.

Records: /home/dev/projects/cym-messenger-047/parent-final-verification.json. Physical acceptance NOT_RUN.

# CYM offline defensive validation (v2.15.65)

## Operator commands (OFFLINE; no radio backend)

Run on the authoritative ESP32 development host. This compiles native Linux C executables, not firmware, and does not load an ESP32 radio driver:

```sh
ssh dev@esp32-dev.gat.ink
cd /home/dev/projects/CYM-NM28C5-jarvis-ws35-docs
python3 -m unittest discover -s tests -p test_defensive_validation.py -v
cat .hermes/defensive-validation/native.log
cat .hermes/defensive-validation/startup.log
cat .hermes/defensive-validation/unsupported.log
python3 -m unittest discover -s tests -v
```

Expected focused result: seven tests, `OK`. The production-source native replay currently reports:

```
OFFLINE native validation: 1089 checks, 0 failures; no RF backend
OFFLINE detector startup: allocation/init/scan/timer failures, busy callbacks, teardown PASS; no RF backend
OFFLINE unsupported transport: PASS; no RF backend
```

The nearby-format, accepted-start-counter and churn-threshold mutations deliberately return nonzero; their rejection is required for the mutation test to pass. Do not interpret mutation logs containing `FAIL` as a green production failure. The full-suite result is recorded in `.hermes/defensive-validation/full-tests.log`.

## What the executable actually exercises

`tests/test_defensive_validation.py` extracts the current production C functions each time, compiles them with `cc` and UndefinedBehaviorSanitizer, and executes them. There is no independent Python classifier oracle.

* Production BLE Spam timer/start callback and payload tables/builders, including deterministic substitutions for `esp_random` and `esp_fill_random` (LCG seed `0x43594d`). Generated fixture bytes are not captured RF traffic.
* Installed ESP-IDF NimBLE `adv_set_fields` and its serialization helpers, using a bounded host mbuf-append substitute. The exact mbuf bytes are compared with NimBLE flat serialization and an independent simple AD framing wrapper.
* Installed NimBLE `ble_hs_adv_parse_fields` / single-field and UUID parser bodies; the production `wp_is_fast_pair_adv`, `bspam_classify`, `bspam_gap_cb`, and complete production churn/UI timer decision.
* Production detector screen startup and stop functions with deterministic allocation, timer, scan/init and callback-busy substitutions. This is not a FreeRTOS/LVGL concurrency stress test.
* Configure, address generation, normal address assignment, AirTag's second assignment, stop, serialization, mbuf allocation, data configuration, start, EALREADY and timer failures. A fault stops the timer and latches until screen exit; there is no new transport or automatic transmit retry. A failed stop is not retried by the abort helper. Installed NimBLE returns EALREADY after successfully disabling an already-stopped instance; stop treats that as confirmed stopped, while EALREADY from start is never counted as a new start. A stop failure cannot prove the controller ceased RF: the UI reports failure and requests screen exit/teardown.

The actual native files, logs, fixture CSVs and SHA-256 provenance are under `.hermes/defensive-validation/`. `payload-provenance.json` compares baseline/current tables and the builder normalized solely for the added AirTag error check. Payload bytes, cadence, burst/address policy and power settings were not changed.

## Coverage and decision matrix

| Existing source format | Offline classifier | Interpretation |
|---|---|---|
| Apple pairing tables (`0x07`) | Apple | Popup-compatible signature, also emitted by genuine devices |
| Existing 15-byte Apple nearby builder (`4c 00 04 04 2a ...`) | Apple | Narrowly corrected missing coverage; other `0x04` manufacturer data not broadly matched |
| SourApple builder (`0x0f`) | Apple | Source-format match only; no iOS crash qualification |
| Samsung builder (`0x0075`) | Samsung | Existing company-ID match is broad and can match benign Samsung data |
| Google table, service UUID `0xfe2c` | Google | Fast Pair-compatible advertisement, not evidence of unauthorized pairing |
| Windows dynamic manufacturer builder (`0x0006`, subtype `0x03`) | Microsoft | Production name length is 5–10; manufacturer data is 10–15, exceeding the existing classifier's six-byte minimum |
| AirTag (`0x12` manufacturer data) | None | Tracking signature deliberately excluded from popup churn |
| SmartTag (`0xfd5a` service data) | None | Tracking signature deliberately excluded from popup churn |

Apple's older `0x01` match remains unchanged. Samsung's company-only breadth and Google's UUID-only breadth are documented, not represented as precise attack attribution. Truncated/malformed AD, benign Apple data and unrelated Apple `0x04` data are negative controls; benign Samsung company data deliberately demonstrates the existing false-positive boundary.

The same exact Apple bytes are replayed with one stable address 1,000 times versus distinct addresses through both legacy and extended discovery callback branches. Tests exercise six-second warmup, thirteen versus fourteen new addresses, the inclusive three-second window boundary and expiry/recovery, tracking churn exclusion and the 192-entry capacity bound. Churn measures address observations, not physical transmitters. Table eviction can re-count an established address after capacity is exceeded.

## Parser/transport boundaries and evidence limits

The host HAL accepts advertising start calls; an accepted API call is not proof of transmitted or received packets. The transmit screen now counts `Adv starts`, not `Packets`. Classic/HackerBox builds without the existing extended API report advertising unavailable; patch04's proposed new legacy transmit transport was not enabled.

The production advertising configuration uses the extended API with `legacy_pdu=1`; that does not make its data an arbitrary extended payload. The native mbuf can serialize fields whose combined AD length exceeds legacy's 31-byte budget (notably some Windows name lengths). These are serialization/classifier fixtures, not controller-accepted on-air packets. The real `set_data` can reject them, and the corrected path aborts on that error. No payload shortening, scan-response workaround or transport enhancement was introduced.

The detector processes one supplied discovery report at a time. Legacy ADV and SCAN_RSP are separate reports; this passive scanner does not solicit scan responses and does not merge them. A manufacturer field confined to an unobserved scan response is not validated by replaying an ADV field. Neither HCI delivery nor fragment reassembly nor scan-response reception has been qualified. Extended reports larger than the parser's uint8 length are rejected rather than truncated. The native parser runs in static-UUID configuration; UUID conversion, locks, scheduling, controller calls and display objects are host substitutes, not the complete ESP-IDF runtime.

The immutable #04 proposal's legacy scan-response buffer issue is absent/non-applicable in current firmware: that transport was never implemented here. It is not claimed as a fixed branch.

Offline evidence proves the exercised byte-processing and state decisions. It does not prove over-air reception, prevention/protection of a phone, OS crashes, complete attack coverage, a physical attacker's identity/location, calibrated distance, or runtime radio/display stability. Hardware qualification remains pending.

## Controlled RF qualification protocol — DOCUMENT ONLY

RF setup has not been supplied or approved. Do not transmit or flash based on this document. No operational crash-transmission procedure is provided.

1. Owner documents written authorization, owned receiver/phone inventory, supported OS/firmware versions and a physically isolated/shielded or conducted test arrangement. Verify isolation before any separate approved RF qualification. Stop if containment cannot be established.
2. Record the precise source revision plus uncommitted diff hash, board/profile, installed IDF/NimBLE version, application descriptor and all artifact SHA-256 values. Do not use a source version as proof of package identity.
3. Collect receiver serial logs, initialization/scan state, independent received packet bytes, advertising event/report type, ADV versus scan-response separation, timestamps/timing and addresses. Retain raw original captures with hashes and distinguish them from native generated fixtures.
4. For each separately approved stimulus, compare actually received bytes with the corresponding fixture and record detector observation/verdict and latency. A sender API success alone is insufficient. Do not equate a phone reaction with detector reception.
5. Include genuine vendor devices, stable repeated advertisements, distinct-address churn below/at threshold, initial warmup, quiet recovery, benign Samsung/company-ID controls, tracking formats, malformed inputs where safely available and crowded-room false-positive controls. RSSI is only a matching-signature signal measurement.
6. Exercise screen exit/Home, allocation/init/scan errors, stop and cleanup, restart after exit, callback quiescence, heap/stack high-water values and timer/object lifetime on each controller class. Preserve receiver logs and screen evidence; failures are unavailable/failed, never an all-clear.
7. Terminate all stimuli, confirm advertising stopped using an independent receiver, restore normal networking/radio state and confirm UI/resource recovery. Quarantine failed artifacts and retain the exact source/binary/log bundle for review.

Development publication follows the complete build/test gate and independent parent review. Flashing and RF qualification remain separate, owner-authorized steps. Check the exact source revision and package hashes before hardware qualification.

CYM v3.0.15-zx3 — WS-C5-35 isolated hardware-test candidate

APPLICATION ONLY: flash at 0x10000 with ERASE ALL OFF using primary USB-C.
Use only on WS-C5-35 with the existing matching partition layout. Do not flash on Classic CYD or other boards. No NVS, partition table or bootloader image is included.

Changes: Observer allocation/lifecycle repair; Stop preserves visible results, Home/main releases session tables after safe quiescence. Global log queue payload uses PSRAM on PSRAM boards. Checked hopper startup and board-selected allocations. Opaque QR result popup. Retains the working reusable ZXing decoder and camera-close-before-SD path.

Verification: WS35 firmware built; focused Observer and QR popup host tests passed and were independently rerun; package checksums verified. Broader regression suite is NOT green: legacy harness compatibility, fixtures and release-version assumptions remain unresolved. This is an explicitly requested test artifact, not a canonical release or proof of hardware acceptance. Clock/mDNS/NTP startup failures and broader Stable BLE/Wi-Fi reports are NOT claimed fixed.

Test both Classic and Modern UI layouts on this WS35: scan/save/Scan Again; Observer start/results/Stop (retain results); Home/main (release session); reopen QR; repeat. Capture primary USB-C diagnostics around transitions. Do not erase NVS or format SD.

Canonical Dev and Stable are unchanged. Third-party licenses accompany the application. No private captures or decoded payloads are included.

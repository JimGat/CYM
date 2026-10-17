# QR engine provenance

ZXing-C++ 3.1.1, upstream https://github.com/zxing-cpp/zxing-cpp
Pinned commit: 287c85df6f961c8efbfb5ffd736cd9457b8b890e.
Vendored bytes and symlinks are unchanged from the verified candidate inventory.
Upstream LICENSE (Apache-2.0) is retained in third_party/zxing-cpp/LICENSE.
The unused zint writer submodule is not imported; writers and non-QR readers
are compiled out by zxing-options.cmake. Existing quirc source/license remain
for historical regression evidence; firmware uses only the WS-C5-35 ZXing path.
The C-compatible adapter is independent of LVGL, camera, SD, and GPIO.
Scoped copied archives rebind allocation, not installed toolchain/runtime files.
The exception emergency reserve retains its original object/ABI with only its
allocation reference routed to PSRAM on WS-C5-35. See eh-runtime.cmake.

Pinned-engine limitation: ZXing DecoderResult::isValid excludes genuinely empty
content. An empty QR symbol is therefore reported as not found, unlike quirc.
Non-empty binary data including a zero byte round-trips; UI/record handling of a
valid zero-length result is still tested independently. No upstream byte edits.

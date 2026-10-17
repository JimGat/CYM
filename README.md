# WS-C5-35 v3.0.14-zx2 application-only hardware test

Artifact-only branch, not buildable source or a Dev/Stable release.

Flash app at 0x10000, erase-all OFF, primary USB-C, existing matching CYM WS35 partition layout. No bootloader/NVS/partition writes.

Repair: C++ exception reserve allocated in PSRAM; existing task-only RF433 sample copy in PSRAM while ISR ring remains internal. Recover 8200 static internal bytes and route 2048 requested arena bytes externally. Runtime memory and physical SD/QR acceptance pending; no on-device success claimed. QR safety admission unchanged.

Capture boot through SD mount before opening QR. Expected arena_after success=1, SD mem_boundary=before_mount resource counters, then Mount SUCCESS at20MHz. Enable debug on before QR; capture decoder_init/camera_open and recognition/save/reopen. Do not format/change card or lower clock.

Native decoder replay and allocation-boundary target tests pass; actual hardware unverified. Complete source/evidence retained on ESP32-Dev under /home/dev/projects/cym-zxing-real-test-evidence/source. ZXing upstream287c85df6f961c8efbfb5ffd736cd9457b8b890e.

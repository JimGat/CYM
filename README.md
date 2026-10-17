# WS-C5-35 ZXing hardware-test download

Artifact-only branch, not a source integration or release. Dev and Stable are unchanged.

Version v3.0.13-zx1, Waveshare ESP32-C5-Touch-LCD-3.5 only. Native and target build verified; physical runtime not verified.

Flash ONLY the application at 0x10000 with erase-all OFF through primary USB-C on the existing compatible CYM partition layout. No bootloader/partition/NVS writes.

Decoder startup safely refuses if free internal RAM is below 8192 bytes or largest internal block below 4096 bytes. Earlier device logs were below these thresholds; recognition on hardware is not guaranteed. Capture decoder_runtime_admission and memory diagnostics if refused.

Built from isolated source based on 003d4b25266d525783d9f9649275e2578f006d88 plus pending camera diagnostics and reusable ZXing adapter; ZXing pin 287c85df6f961c8efbfb5ffd736cd9457b8b890e. Complete source/evidence retained on ESP32-Dev at /home/dev/projects/cym-zxing-real-test-evidence/source. This branch contains the requested application download only, not its buildable source tree.
